import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
import tempfile
from openpyxl import load_workbook
from PyQt5.QtWidgets import QApplication, QSizePolicy, QPushButton
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextTable
import db
import auth
import logic
from ui.availability import init_availability, unavailable
from ui.login import LoginDialog
from ui.main_window import MainWindow
from ui.style import build_qss

app=QApplication.instance() or QApplication([])
app.setStyleSheet(build_qss())


class SystemTests(unittest.TestCase):
    def setUp(self):
        db.init(':memory:'); db.seed(); auth.init(); init_availability()

    def tearDown(self):
        db.conn.close()

    def test_authentication(self):
        auth.create('secretary','correct-password')
        self.assertTrue(auth.verify('secretary','correct-password'))
        self.assertFalse(auth.verify('secretary','wrong-password'))
        self.assertFalse(auth.verify('missing','correct-password'))
        stored=db.row('SELECT * FROM users')
        self.assertNotEqual(stored['digest'],'correct-password')
        with self.assertRaises(ValueError): auth.create('other','short')

    def test_login_ui(self):
        login=LoginDialog(); login.show()
        login.username.setText('registrar'); login.password.setText('password-123')
        QTest.mouseClick(login.submit,Qt.LeftButton); self.assertEqual(login.result(),1)
        second=LoginDialog(); second.username.setText('registrar'); second.password.setText('incorrect'); second.login()
        self.assertFalse(second.error.isHidden()); self.assertEqual(second.result(),0)
        second.password.setText('password-123'); second.login(); self.assertEqual(second.result(),1)

    def test_schedule_conflicts(self):
        r=logic.schedule_rows(1)[0]
        issues=logic.check_candidate(1,r['subject_id'],r['section_id'],r['faculty_id'],r['room_id'],[r['day']],r['start_min'],r['end_min'])
        self.assertTrue({'Faculty Conflict','Classroom Conflict','Section Conflict'} <= {i['type'] for i in issues})
        self.assertFalse(logic.overlap(480,540,540,600))
        self.assertEqual(logic.check_candidate(1,r['subject_id'],r['section_id'],r['faculty_id'],r['room_id'],['Mon'],600,500)[0]['type'],'Invalid Time')

    def test_availability_and_persistence(self):
        r=logic.schedule_rows(1)[0]
        with db.conn:
            db.conn.execute('INSERT INTO unavailable(kind,resource_id,day,start_min,end_min) VALUES(?,?,?,?,?)',('faculty',r['faculty_id'],'Sat',480,600))
        self.assertTrue(unavailable('faculty',r['faculty_id'],'Sat',500,550))
        issues=logic.check_candidate(1,r['subject_id'],r['section_id'],r['faculty_id'],r['room_id'],['Sat'],480,570)
        self.assertIn('Unavailable Resource',{i['type'] for i in issues})
        before=len(logic.schedule_rows(1)); logic.save_schedule(1,r['subject_id'],r['section_id'],r['faculty_id'],r['room_id'],['Sat'],660,720)
        new=db.row('SELECT MAX(id) FROM schedules')[0]; self.assertEqual(len(logic.schedule_rows(1)),before+1)
        logic.delete_schedules(1,[new]); self.assertEqual(len(logic.schedule_rows(1)),before)
        result=logic.validate_term(1); self.assertGreater(result['critical'],0); self.assertLess(result['score'],100)

    def test_empty_database_workflow(self):
        db.conn.close(); db.init(':memory:'); auth.init(); init_availability()
        win=MainWindow(); win.show(); app.processEvents()
        for key in win.pages:
            win.go(key); app.processEvents()
        self.assertEqual(logic.validate_term(win.term_id())['total'],0)
        page=win.pages['academic']; page.set_tab('programs')
        combo=page.form.widgets['name']; combo.setCurrentIndex(0)
        page.save()
        self.assertEqual(db.row('SELECT COUNT(*) FROM programs')[0],1)
        win.close()

    def test_schedule_editor_create_edit_delete(self):
        win=MainWindow(); page=win.pages['schedules']; page.refresh()
        for key,value in [('days','Sat'),('start',780),('end',840)]:
            page.fields[key].setCurrentIndex(page.fields[key].findData(value))
        before=db.row('SELECT COUNT(*) FROM schedules')[0]
        with tempfile.TemporaryDirectory() as directory, patch(
            'ui.reports.QStandardPaths.writableLocation', return_value=directory
        ):
            page.save()
            self.assertEqual(db.row('SELECT COUNT(*) FROM schedules')[0],before+1)
            device_pdf=os.path.join(directory,'ClassFlow','Schedules','ClassFlow-schedule-sheet-term-1.pdf')
            self.assertGreater(os.path.getsize(device_pdf),1000)
            record=db.row('SELECT MAX(id) FROM schedules')[0]
            page.open(edit_ids=[record])
            page.fields['end'].setCurrentIndex(page.fields['end'].findData(870))
            page.save()
            self.assertEqual(db.row('SELECT COUNT(*) FROM schedules')[0],before+1)
            edited=db.row('SELECT * FROM schedules WHERE day="Sat"')
            self.assertEqual(edited['end_min'],870)
            group=next(g for g in logic.group_rows(logic.schedule_rows(1)) if edited['id'] in g['ids'])
            from PyQt5.QtWidgets import QMessageBox
            with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes): page.delete(group)
            self.assertEqual(db.row('SELECT COUNT(*) FROM schedules')[0],before)
            self.assertGreater(os.path.getsize(device_pdf),1000)
        win.close()

    def test_room_utilization_schedule_includes_all_room_occupants(self):
        win=MainWindow()
        reports=win.pages['reports']
        reports.refresh()
        room=db.row('SELECT id FROM classrooms WHERE name="Room 103"')['id']
        reports.room.setCurrentIndex(reports.room.findData(room))
        reports.report.setCurrentIndex(reports.report.findText('Room Utilization Schedule'))
        self.assertEqual(reports.program.currentText(), 'All programs')
        self.assertEqual(reports.section.currentText(), 'All sections')
        self.assertEqual(reports.faculty.currentText(), 'All faculty')
        self.assertTrue(all(not combo.isEnabled() for combo in (
            reports.program, reports.section, reports.faculty,
        )))
        self.assertFalse(any(reports.room.itemText(i).lower().startswith('all') for i in range(reports.room.count())))
        reports.program.setCurrentIndex(reports.program.findData(
            db.row('SELECT id FROM programs WHERE code="BSIT"')['id']
        ))
        reports.faculty.setCurrentIndex(reports.faculty.findData(
            db.row('SELECT id FROM faculty WHERE name="Prof. Miguel Cruz"')['id']
        ))
        reports.section.setCurrentIndex(reports.section.findData(
            db.row('SELECT id FROM sections WHERE name="BSIT 2B"')['id']
        ))
        expected={r['id'] for r in logic.schedule_rows(1) if r['room_id']==room}
        self.assertEqual({r['id'] for r in reports.report_rows},expected)
        self.assertGreater(len({r['section_id'] for r in reports.report_rows}),1)
        with db.conn:
            db.conn.execute(
                'INSERT INTO unavailable(kind,resource_id,day,start_min,end_min) VALUES(?,?,?,?,?)',
                ('room',room,'Sat',480,540),
            )
        reports.render()
        statuses={row[4] for row in reports.output}
        self.assertIn('Available',statuses)
        self.assertIn('Unavailable',statuses)
        sheet=reports.room_utilization_html()
        self.assertIn('ROOM UTILIZATION SCHEDULE',sheet)
        self.assertIn('SATURDAY',sheet)
        self.assertIn('bgcolor="#ffffff"',sheet)
        self.assertIn('color="#000000"',sheet)
        self.assertNotIn('#e8eff8',sheet)
        self.assertNotIn('#fce8d4',sheet)
        self.assertNotIn('<b>AVAILABLE</b>',sheet)
        self.assertIn('>TIME</th>',sheet)
        self.assertIn('>MONDAY</th>',sheet)
        self.assertIn(
            '<td rowspan="1" height="18" bgcolor="#ffffff" align="center" valign="middle">'
            '<font size="2" color="#000000"></font></td>',
            sheet,
        )
        self.assertIn('UNAVAILABLE',sheet)
        self.assertIn('BSCS 1A',sheet)
        self.assertIn('Dr. Elena Santos',sheet)
        self.assertNotIn('Room 104',sheet)
        win.close()

    def test_academic_faculty_creation(self):
        win=MainWindow(); page=win.pages['academic']; page.set_tab('faculty')
        page.form.widgets['name'].setText('Prof. Test Faculty')
        page.form.widgets['department'].setText('Computer Science')
        page.form.widgets['email'].setText('faculty@example.edu')
        page.save()
        self.assertIsNotNone(db.row('SELECT * FROM faculty WHERE name=?',('Prof. Test Faculty',)))
        win.close()

    def test_exports_and_auth_disk_persistence(self):
        win=MainWindow(); reports=win.pages['reports']; reports.refresh()
        with tempfile.TemporaryDirectory() as directory:
            pdf=os.path.join(directory,'report.pdf')
            excel_path=os.path.join(directory,'schedule.xlsx')
            reports.room.setCurrentIndex(reports.room.findData(
                db.row('SELECT id FROM classrooms WHERE name="Room 103"')['id']
            ))
            schedule_html = reports.room_utilization_html()
            self.assertIn('<th width="15.00%" nowrap="nowrap">FRIDAY</th>', schedule_html)
            self.assertIn('align="center" nowrap="nowrap">', schedule_html)
            with patch('ui.reports.QFileDialog.getSaveFileName',return_value=(pdf,'PDF')):
                with patch.object(
                    reports, 'print_schedule_pdf', wraps=reports.print_schedule_pdf
                ) as pdf_layout:
                    reports.export_pdf()
            pdf_document=pdf_layout.call_args.args[1]
            frames=[pdf_document.rootFrame()]
            grid_tables=[]
            while frames:
                frame=frames.pop()
                for child in frame.childFrames():
                    if isinstance(child,QTextTable) and child.columns()==len(db.DAYS)+1:
                        grid_tables.append(child)
                    frames.append(child)
            self.assertTrue(grid_tables)
            self.assertGreaterEqual(
                pdf_document.documentLayout().frameBoundingRect(grid_tables[0]).width(),
                pdf_document.textWidth()*0.95,
            )
            with patch('ui.reports.QFileDialog.getSaveFileName',return_value=(excel_path,'Excel')): reports.export_excel()
            self.assertGreater(os.path.getsize(pdf),1000)
            workbook=load_workbook(excel_path,data_only=True)
            sheet=workbook['Class Schedule']
            self.assertEqual(sheet['A1'].value,'ROOM UTILIZATION SCHEDULE')
            self.assertEqual(sheet['A6'].value,'PERIOD')
            self.assertEqual(sheet['B6'].value,'MONDAY')
            self.assertEqual(sheet['A7'].value, f'{logic.fmt(logic.CAL_START)}–{logic.fmt(logic.CAL_START+30)}')
            self.assertTrue(sheet.merged_cells.ranges)
            self.assertIsNone(sheet.freeze_panes)
            self.assertTrue(sheet.sheet_view.showGridLines)
            self.assertIn('1st year', [sheet.cell(5, column).value for column in range(2, 8)])
            self.assertIn('2nd year', [sheet.cell(5, column).value for column in range(2, 8)])
            year_fills = {
                cell.fill.fgColor.rgb[-6:]
                for row in sheet.iter_rows(min_row=7, min_col=2, max_col=7)
                for cell in row
                if cell.value and cell.fill.fgColor.type == 'rgb'
            }
            self.assertTrue({'FCE4D6', 'FFF2CC'}.issubset(year_fills))
            workbook.close()
            reports.report.setCurrentIndex(reports.report.findText('Section Schedules'))
            class_excel_path=os.path.join(directory,'class-schedule.xlsx')
            with patch('ui.reports.QFileDialog.getSaveFileName',return_value=(class_excel_path,'Excel')): reports.export_excel()
            workbook=load_workbook(class_excel_path,data_only=True)
            sheet=workbook['Class Schedule']
            self.assertEqual(sheet['A1'].value,'CLASS SCHEDULE')
            self.assertIn('Section:',sheet['E4'].value)
            self.assertTrue(any(
                isinstance(sheet.cell(row,column).value,str) and ' · ' in sheet.cell(row,column).value
                for row in range(7,sheet.max_row+1)
                for column in range(2,8)
            ))
            workbook.close()
        win.close()
        db.conn.close()
        with tempfile.TemporaryDirectory() as directory:
            path=directory+'/test.db'; db.init(path); auth.init(); auth.create('admin','persistent-password'); db.conn.close()
            db.init(path); auth.init(); self.assertTrue(auth.verify('admin','persistent-password')); db.conn.close()
        db.init(':memory:')
        # tearDown closes the connection.

    def test_schedule_report_filters_only_offer_specific_choices(self):
        win=MainWindow(); reports=win.pages['reports']; reports.refresh()
        for report_name in ('Class Schedules', 'Faculty Schedules', 'Section Schedules'):
            reports.report.setCurrentIndex(reports.report.findText(report_name))
            for combo in (reports.program, reports.section, reports.faculty):
                self.assertTrue(all(combo.itemData(i) is not None for i in range(combo.count())))
                self.assertTrue(all(not combo.itemText(i).lower().startswith('all') for i in range(combo.count())))
                self.assertIsNotNone(combo.currentData())

        reports.report.setCurrentIndex(reports.report.findText('Room Utilization Schedule'))
        self.assertEqual(reports.program.currentText(), 'All programs')
        self.assertEqual(reports.section.currentText(), 'All sections')
        self.assertEqual(reports.faculty.currentText(), 'All faculty')
        self.assertTrue(all(not combo.isEnabled() for combo in (
            reports.program, reports.section, reports.faculty,
        )))
        win.close()

    def test_all_pages_and_report(self):
        win=MainWindow(); win.show(); app.processEvents()
        for key in win.pages:
            win.go(key); app.processEvents(); self.assertEqual(win.stack.currentWidget(),win.pages[key])
        reports=win.pages['reports']
        for i in range(reports.report.count()):
            reports.report.setCurrentIndex(i); app.processEvents(); self.assertTrue(reports.headers)
        reports.report.setCurrentIndex(2)
        sheet=reports.schedule_sheet_html()
        self.assertIn('>PERIOD</th>',sheet)
        self.assertIn('>MONDAY</th>',sheet)
        self.assertIn('BSCS 2A',sheet)
        self.assertIn('2nd year',sheet)
        self.assertIn(
            f'{logic.fmt(logic.CAL_START)} - {logic.fmt(logic.CAL_START + 30)}',
            sheet,
        )
        self.assertEqual(sheet.count('<td height="20" align="center" nowrap="nowrap">'),26)
        self.assertEqual(sheet.count('<tr height="20">'),26)
        self.assertIn('rowspan=',sheet)
        for row in reports.report_rows:
            for key in ('code','section','faculty','room'):
                self.assertIn(row[key],sheet)
        self.assertEqual(reports.calendar.sizePolicy().verticalPolicy(),QSizePolicy.Fixed)
        self.assertNotIn('Generate Timetable',[b.text() for b in reports.findChildren(QPushButton)])
        pdf_path=os.path.join(tempfile.gettempdir(),'classflow-report-test.pdf')
        printer=QPrinter(QPrinter.HighResolution); printer.setOutputFormat(QPrinter.PdfFormat); printer.setOutputFileName(pdf_path)
        document=reports.document()
        reports.print_schedule_pdf(printer,document)
        self.assertGreater(os.path.getsize(pdf_path),1000)
        grid=next(
            frame for frame in document.rootFrame().childFrames()
            if isinstance(frame,QTextTable) and frame.columns()==len(db.DAYS)+1
        )
        self.assertGreaterEqual(
            document.documentLayout().frameBoundingRect(grid).width(),
            printer.pageRect(QPrinter.Point).width()*0.95,
        )
        column_widths=[width.value(100) for width in grid.format().columnWidthConstraints()]
        self.assertAlmostEqual(column_widths[0],17)
        self.assertTrue(all(abs(width-column_widths[1])<0.01 for width in column_widths[1:]))
        # Capture each actual UI for visual inspection.
        for key in win.pages:
            win.go(key); app.processEvents(); win.grab().save(os.path.join(tempfile.gettempdir(),'classflow-'+key+'.png'))
        win.close()

    def test_report_conflict_warning_opens_validation(self):
        win=MainWindow(); win.show(); win.go('reports'); app.processEvents()
        reports=win.pages['reports']
        self.assertIn('Resolve critical conflicts',reports.banner.title.text())
        self.assertTrue(reports.resolve_button.isVisible())
        QTest.mouseClick(reports.resolve_button,Qt.LeftButton)
        self.assertEqual(win.stack.currentWidget(),win.pages['validation'])
        self.assertGreater(win.pages['validation'].result['critical'],0)
        win.close()


if __name__=='__main__': unittest.main()
