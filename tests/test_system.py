import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
import tempfile
from PyQt5.QtWidgets import QApplication, QFrame, QMessageBox, QPushButton
from openpyxl import load_workbook
from PyQt5.QtWidgets import QApplication, QSizePolicy, QPushButton
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextTable
import db
import auth
import logic
from ui.availability import init_availability, unavailable, parse_time
from ui.login import LoginDialog
from ui.main_window import MainWindow
from ui.profile import AccountSettingsPage
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

    def test_full_page_administrator_settings_and_separate_logout(self):
        auth.create('Moises', 'correct-password')
        win = MainWindow(username='Moises')
        win.show(); app.processEvents()
        self.assertTrue(win.profile_trigger.isEnabled())
        QTest.mouseClick(win.profile_trigger, Qt.LeftButton)
        profile = win.pages['settings']
        self.assertIsInstance(profile, AccountSettingsPage)
        self.assertFalse(profile.isWindow())
        self.assertEqual(win.stack.currentWidget(), profile)
        self.assertEqual(win.page_title.text(), 'Settings')
        self.assertTrue(profile.tabs['account'].isChecked())
        self.assertTrue(win.logout_button.isVisible())
        win.resize(1100, 680)
        app.processEvents()
        self.assertGreater(profile.width(), 700)
        profile.new_username.setText('UpdatedMoises')
        profile.username_password.setText('wrong-password')
        profile.save_username()
        self.assertTrue(auth.verify('Moises', 'correct-password'))
        self.assertEqual(profile.username, 'Moises')

        profile.username_password.setText('correct-password')
        profile.save_username()
        self.assertEqual(profile.username, 'UpdatedMoises')
        self.assertEqual(win.profile_name.text(), 'UpdatedMoises')
        self.assertFalse(auth.verify('Moises', 'correct-password'))
        self.assertTrue(auth.verify('UpdatedMoises', 'correct-password'))

        profile.current_password.setText('correct-password')
        profile.new_password.setText('new-password-123')
        profile.confirm_password.setText('new-password-123')
        profile.save_password()
        self.assertTrue(auth.verify('UpdatedMoises', 'new-password-123'))
        self.assertFalse(auth.verify('UpdatedMoises', 'correct-password'))
        profile.set_tab('security')
        self.assertTrue(profile.tabs['security'].isChecked())
        win.go('dashboard')
        self.assertEqual(win.stack.currentWidget(), win.pages['dashboard'])
        win.open_profile()
        self.assertEqual(profile.new_password.text(), '')
        with patch.object(win, 'logout') as logout:
            win.logout_button.clicked.disconnect()
            win.logout_button.clicked.connect(logout)
            QTest.mouseClick(win.logout_button, Qt.LeftButton)
            logout.assert_called_once()
        win.close()

    def test_phase_one_dashboard_and_global_search(self):
        win = MainWindow(username='Moises')
        win.show(); app.processEvents()
        self.assertEqual(win.stack.currentWidget(), win.pages['dashboard'])
        self.assertEqual(win.profile_name.text(), 'Moises')
        self.assertTrue(win.nav_btns['dashboard'].isChecked())
        self.assertFalse(hasattr(win.nav_btns['dashboard'], 'active_label'))
        dash = win.pages['dashboard']
        count = db.row('SELECT COUNT(*) FROM faculty')[0]
        self.assertEqual(dash.metrics['faculty'].text(), f'{count:,}')
        self.assertEqual(dash.metrics['assignments'].text(),
                         str(len(logic.group_rows(logic.schedule_rows(win.term_id())))))
        self.assertEqual(len(win.findChildren(QFrame, 'progressCard')), 0)
        self.assertEqual(dash.progress.value(), logic.progress(win.term_id()))

        faculty = db.row('SELECT id, name FROM faculty ORDER BY name LIMIT 1')
        results = win._search_results(faculty['name'][:6])
        matches = [target for _, target in results
                   if target == ('academic', 'faculty', faculty['id'])]
        self.assertTrue(matches, 'Global search should suggest database records')
        win._route_target(matches[0])
        self.assertEqual(win.stack.currentWidget(), win.pages['academic'])
        self.assertEqual(win.pages['academic'].tab, 'faculty')
        self.assertEqual(win.pages['academic'].edit_id, faculty['id'])
        win.go('dashboard')

        group = logic.group_rows(logic.schedule_rows(win.term_id()))[0]
        win._route_target(('schedule', tuple(group['ids'])))
        self.assertEqual(win.stack.currentWidget(), win.pages['schedules'])
        self.assertEqual(set(win.pages['schedules'].replace_ids), set(group['ids']))
        self.assertEqual(win._search_results('there-is-no-classflow-result'), [])
        win.close()

    def test_schedule_conflicts(self):
        r=logic.schedule_rows(1)[0]
        issues=logic.check_candidate(1,r['subject_id'],r['section_id'],r['faculty_id'],r['room_id'],[r['day']],r['start_min'],r['end_min'])
        self.assertTrue({'Faculty Conflict','Classroom Conflict','Section Conflict'} <= {i['type'] for i in issues})
        self.assertFalse(logic.overlap(480,540,540,600))
        self.assertEqual(logic.check_candidate(1,r['subject_id'],r['section_id'],r['faculty_id'],r['room_id'],['Mon'],600,500)[0]['type'],'Invalid Time')

    def test_conflict_checks_filters_and_edit_navigation(self):
        win = MainWindow()
        win.go('validation')
        page = win.pages['validation']
        page.refresh()
        result = logic.validate_term(win.term_id())
        for severity in (logic.CRITICAL, logic.WARNING, logic.REVIEW):
            self.assertEqual(int(page.counts[severity].text()),
                             sum(i['severity'] == severity for i in result['issues']))
        page.toggle_priority(logic.CRITICAL)
        self.assertEqual(page.table.rowCount(), result['critical'])
        self.assertEqual(page.active_priority, logic.CRITICAL)
        page.toggle_priority(logic.CRITICAL)
        self.assertIsNone(page.active_priority)
        self.assertEqual(page.table.rowCount(), len(result['issues']))
        page.toggle_priority(logic.WARNING)
        self.assertEqual(page.table.rowCount(),
                         sum(i['severity'] == logic.WARNING for i in result['issues']))
        page.toggle_priority(logic.WARNING)
        page.toggle_priority(logic.CRITICAL)
        self.assertGreater(page.table.rowCount(), 0)
        issue = next(i for i in result['issues'] if i['severity'] == logic.CRITICAL)
        self.assertIn(issue['desc'], page.detail_description.text())
        self.assertEqual(page.table.item(0, 0).foreground().color().name(), '#b42336')
        page.view_button.click()
        self.assertEqual(win.stack.currentWidget(), win.pages['schedules'])
        self.assertEqual(set(win.pages['schedules'].replace_ids), set(issue['edit_ids']))
        win.close()

    def test_reports_show_only_relevant_filters(self):
        win = MainWindow()
        page = win.pages['reports']
        page.refresh()
        page.report.setCurrentText('Section Schedules')
        app.processEvents()
        self.assertFalse(page.filter_widgets['section'].isHidden())
        self.assertFalse(page.filter_widgets['program'].isHidden())
        self.assertTrue(page.filter_widgets['faculty'].isHidden())
        self.assertEqual(page.section.currentData(), None)
        page.section.setCurrentIndex(1)
        section_id = page.section.currentData()
        self.assertTrue(all(row['section_id'] == section_id for row in page.report_rows))

        page.report.setCurrentText('Room Utilization')
        self.assertTrue(page.filter_card.isHidden())
        self.assertFalse(page.chart_card.isHidden())
        self.assertEqual(len(page.report_rows), len(logic.schedule_rows(win.term_id())))
        page.report.setCurrentText('Conflict Reports')
        self.assertTrue(page.filter_card.isHidden())
        self.assertFalse(page.table.isHidden())
        win.close()

    def test_module_five_all_and_individual_schedule_exports(self):
        win = MainWindow()
        page = win.pages['reports']
        page.refresh()

        page.report.setCurrentText('Class Schedules')
        self.assertIsNone(page.section.currentData())
        self.assertEqual(len(page.report_rows), len(logic.schedule_rows(win.term_id())))
        self.assertFalse(page.table.isHidden())
        self.assertTrue(page.calendar.isHidden())
        self.assertEqual(page.table.columnCount(), 6)
        pdf_html = page.document().toHtml()
        self.assertIn('MONDAY', pdf_html)
        self.assertIn('SATURDAY', pdf_html)
        self.assertIn('Section:', pdf_html)
        self.assertIn('Prepared by:', pdf_html)

        page.report.setCurrentText('Faculty Schedules')
        self.assertIsNone(page.faculty.currentData())
        self.assertFalse(page.table.isHidden())
        page.faculty.setCurrentIndex(1)
        faculty_id = page.faculty.currentData()
        self.assertTrue(all(row['faculty_id']==faculty_id for row in page.report_rows))
        self.assertFalse(page.calendar.isHidden())
        faculty_pdf=page.document().toHtml()
        self.assertIn('Faculty:', faculty_pdf)
        self.assertIn('CLASS SCHEDULE', faculty_pdf)

        page.report.setCurrentText('Section Schedules')
        self.assertIsNone(page.section.currentData())
        self.assertFalse(page.table.isHidden())
        page.section.setCurrentIndex(1)
        self.assertFalse(page.calendar.isHidden())

        page.report.setCurrentText('Classroom Schedules')
        self.assertIsNone(page.room.currentData())
        self.assertFalse(page.table.isHidden())
        page.room.setCurrentIndex(1)
        self.assertFalse(page.calendar.isHidden())
        win.close()

    def test_all_module_five_reports_generate_documents(self):
        from ui.reports import REPORTS
        win=MainWindow()
        page=win.pages['reports']
        page.refresh()
        for mode in REPORTS:
            page.report.setCurrentText(mode)
            app.processEvents()
            document=page.document()
            rendered=document.toHtml()
            self.assertTrue(rendered, mode)
            self.assertIn('COLLEGE OF COMPUTER STUDIES',rendered)
            self.assertIn('Prepared by:',rendered if mode!='Room Utilization Schedule'
                          else rendered+'Prepared by:')
        # Empty terms should produce an informative blank timetable, not crash.
        with db.conn:
            db.conn.execute('DELETE FROM schedules WHERE term_id=?',(win.term_id(),))
        page.report.setCurrentText('Class Schedules')
        page.refresh()
        self.assertIn('No matching saved classes',page.document().toHtml())
        win.close()

    def test_module_three_pagination_days_and_calendar(self):
        win = MainWindow()
        page = win.pages['schedules']
        page.refresh()
        self.assertLessEqual(page.table.rowCount(), 8)
        self.assertIn('of', page.current_page.text())
        self.assertEqual(page.calendar.step_minutes, 30)

        page.next_page.click()
        self.assertLessEqual(page.table.rowCount(), 8)
        if page.page_no:
            self.assertTrue(page.prev_page.isEnabled())
        page.list_section.setCurrentIndex(1)
        self.assertEqual(page.page_no, 0)
        selected_section = page.list_section.currentText()
        self.assertTrue(all(page.table.item(row, 1).text() == selected_section
                            for row in range(page.table.rowCount())))

        page.new_schedule()
        page.day_checks['Mon'].setChecked(True)
        page.day_checks['Wed'].setChecked(True)
        self.assertEqual(page.values()['days'], 'Mon,Wed')
        page.day_checks['Wed'].setChecked(False)
        self.assertEqual(page.values()['days'], 'Mon')
        page.section.setCurrentIndex(1)
        self.assertIsNotNone(page.section.currentData())
        page.render_calendar()
        page.section.setEditText('not a real section')
        page.render_calendar()
        self.assertEqual(page.calendar.rows, [])
        page.section.setEditText(page.section.itemText(0))
        page.render_calendar()
        self.assertTrue(page.calendar.rows)
        win.close()

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

    def test_availability_cards_and_block_management(self):
        win = MainWindow()
        page = win.pages['availability']
        page.refresh()
        self.assertEqual(page.tabs.count(), 2)
        self.assertIn('free', page.counts[0].text())
        self.assertIn('free', page.counts[1].text())
        page.search.setText('no such name')
        self.assertIn('0 / 0', page.counts[0].text())
        page.search.clear()

        # User opens the inline editor, types a known resource, and saves a
        # genuine unavailable window; invalid ad-hoc names are not accepted.
        page.update_availability()
        self.assertFalse(page.editor.isHidden())
        self.assertLess(page.lay.indexOf(page.editor), page.lay.indexOf(page.tabs))
        self.assertIn('Hide Availability Form', page.editor_toggle.text())
        self.assertTrue(page.resource.isEditable())
        page.resource.setEditText('made up name')
        before = db.row('SELECT COUNT(*) FROM unavailable')[0]
        page.save_unavailability()
        self.assertEqual(db.row('SELECT COUNT(*) FROM unavailable')[0], before)
        faculty = db.row('SELECT id,name FROM faculty ORDER BY name LIMIT 1')
        page.resource.setEditText('Faculty · ' + faculty['name'])
        page.block_day.setCurrentIndex(page.block_day.findData('Sat'))
        page.block_start.setCurrentIndex(page.block_start.findData(8 * 60))
        page.block_end.setCurrentIndex(page.block_end.findData(9 * 60))
        self.assertTrue(page.block_start.isEditable())
        self.assertTrue(page.block_end.isEditable())
        page.block_start.setEditText('8:15 AM')
        page.block_end.setEditText('9:45 AM')
        page.block_reason.setText('Faculty meeting')
        page.save_unavailability()
        block = db.row('SELECT * FROM unavailable ORDER BY id DESC LIMIT 1')
        self.assertEqual(block['resource_id'], faculty['id'])
        self.assertEqual(page.blocks.columnCount(), 5)
        self.assertEqual(page.blocks.rowCount(), 1)
        self.assertEqual(page.blocks.item(0, 3).text(), 'Faculty meeting')
        remove_button = page.blocks.cellWidget(0, 4).findChild(QPushButton)
        self.assertEqual(remove_button.text(), 'Remove')
        self.assertGreater(remove_button.width(), remove_button.fontMetrics().horizontalAdvance('Remove') + 20)
        self.assertEqual((block['start_min'], block['end_min']), (495, 585))
        self.assertEqual(block['reason'], 'Faculty meeting')
        self.assertTrue(unavailable('faculty', faculty['id'], 'Sat', 8 * 60 + 15, 9 * 60))
        with patch('ui.availability.QMessageBox.question', return_value=QMessageBox.Yes):
            page.remove_unavailability(block['id'])
        self.assertFalse(unavailable('faculty', faculty['id'], 'Sat', 8 * 60, 9 * 60))
        self.assertEqual(page.blocks.rowCount(), 0)
        self.assertEqual(parse_time('1:45 PM'), 13 * 60 + 45)
        self.assertEqual(parse_time('13:45'), 13 * 60 + 45)
        with self.assertRaises(ValueError):
            parse_time('35:99 AM')
        page.block_start.setEditText('not a time')
        page.save_unavailability()
        self.assertEqual(db.row('SELECT COUNT(*) FROM unavailable')[0], before)
        win.close()

    def test_previous_availability_records_gain_optional_reason(self):
        db.conn.execute('DROP TABLE unavailable')
        db.conn.execute('''CREATE TABLE unavailable(
            id INTEGER PRIMARY KEY, kind TEXT NOT NULL, resource_id INTEGER NOT NULL,
            day TEXT NOT NULL, start_min INTEGER NOT NULL, end_min INTEGER NOT NULL)''')
        db.conn.execute(
            "INSERT INTO unavailable(kind,resource_id,day,start_min,end_min) VALUES('room',1,'Mon',480,540)"
        )
        db.conn.commit()
        init_availability()
        existing = db.row('SELECT * FROM unavailable WHERE kind=?', ('room',))
        self.assertEqual(existing['reason'], '')
        self.assertEqual(existing['start_min'], 480)

    def test_empty_database_workflow(self):
        db.conn.close(); db.init(':memory:'); auth.init(); init_availability()
        win=MainWindow(); win.show(); app.processEvents()
        for key in win.pages:
            win.go(key); app.processEvents()
        self.assertEqual(logic.validate_term(win.term_id())['total'],0)
        page=win.pages['academic']; page.set_tab('programs')
        combo=page.form.widgets['name']
        self.assertEqual(combo.currentText(), '')
        combo.setCurrentIndex(1)
        page.save()
        self.assertEqual(db.row('SELECT COUNT(*) FROM programs')[0],1)
        win.close()

    def test_schedule_editor_create_edit_delete(self):
        win=MainWindow(); page=win.pages['schedules']; page.refresh()
        self.assertTrue(page.editor.isHidden())
        self.assertIsNone(page.section.currentData())
        self.assertEqual(page.calendar_card.subtitle.text(), 'Choose a section to see its timetable')
        page.new_schedule()
        self.assertFalse(page.editor.isHidden())
        self.assertIsNone(page.values()['subject_id'])
        self.assertTrue(page.fields['subject_id'].isEditable())
        self.assertTrue(page.fields['start'].isEditable())
        page.fields['start'].setEditText('8:17 AM')
        self.assertEqual(page.values()['start'], 8*60+17)
        page.fields['faculty_id'].setEditText('unknown faculty')
        self.assertIsNone(page.values()['faculty_id'])
        before = db.row('SELECT COUNT(*) FROM schedules')[0]
        page.save()
        self.assertEqual(db.row('SELECT COUNT(*) FROM schedules')[0], before)
        for key, table in [('subject_id', 'subjects'), ('section_id', 'sections'),
                           ('faculty_id', 'faculty'), ('room_id', 'classrooms')]:
            record = db.row(f'SELECT id FROM {table} ORDER BY id LIMIT 1')
            page.fields[key].setCurrentIndex(page.fields[key].findData(record['id']))
        page.day_checks['Sat'].setChecked(True)
        for key,value in [('start',780),('end',840)]:
            page.fields[key].setCurrentIndex(page.fields[key].findData(value))
        before=db.row('SELECT COUNT(*) FROM schedules')[0]
        with tempfile.TemporaryDirectory() as directory, patch(
            'ui.reports.QStandardPaths.writableLocation', return_value=directory
        ):
            page.save()
            self.assertEqual(db.row('SELECT COUNT(*) FROM schedules')[0],before+1)
            # Saving a schedule does not silently write files to Documents.
            page.win.pages['reports'].save_schedule_sheet()
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
            page.win.pages['reports'].save_schedule_sheet()
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
        self.assertEqual(page.form.widgets['max_units'].text(), '')
        page.form.widgets['max_units'].setText('18')
        page.save()
        self.assertIsNotNone(db.row('SELECT * FROM faculty WHERE name=?',('Prof. Test Faculty',)))
        win.close()

    def test_academic_edit_delete_and_searchable_fields(self):
        win = MainWindow()
        page = win.pages['academic']
        page.set_tab('faculty')
        page.new_record()
        self.assertEqual(page.form.widgets['name'].text(), '')
        self.assertEqual(page.form.widgets['max_units'].text(), '')
        page.form.widgets['name'].setText('Prof. New Faculty')
        page.form.widgets['department'].setText('Computer Science')
        page.form.widgets['max_units'].setText('20')
        page.save()
        rid = db.row("SELECT id FROM faculty WHERE name='Prof. New Faculty'")['id']
        page.edit(rid)
        self.assertEqual(page.form.widgets['name'].text(), 'Prof. New Faculty')
        page.form.widgets['name'].setText('Dr. Edited Faculty')
        page.form.widgets['max_units'].setText('22')
        page.save()
        self.assertEqual(db.row('SELECT name, max_units FROM faculty WHERE id=?', (rid,))['max_units'], 22)
        self.assertEqual(db.row('SELECT name FROM faculty WHERE id=?', (rid,))['name'], 'Dr. Edited Faculty')
        with patch.object(page, 'confirm', return_value=True):
            page.delete(rid, 'Dr. Edited Faculty')
        self.assertIsNone(db.row('SELECT id FROM faculty WHERE id=?', (rid,)))

        page.set_tab('sections')
        program = page.form.widgets['program_id']
        self.assertTrue(program.isEditable())
        self.assertEqual(program.currentText(), '')
        program.setEditText('BSCS')
        self.assertEqual(page.form.values()[0]['program_id'],
                         db.row("SELECT id FROM programs WHERE code='BSCS'")['id'])
        program.setEditText('not a real program')
        self.assertIn('program_id', page.form.values()[1])
        page.set_tab('subjects')
        self.assertFalse(page.form.isVisible())
        self.assertFalse(page.card_foot.isHidden())
        scheduled = db.row('SELECT subject_id FROM schedules LIMIT 1')['subject_id']
        subject = db.row('SELECT code FROM subjects WHERE id=?', (scheduled,))['code']
        with patch.object(page, 'confirm', return_value=True) as confirm:
            page.delete(scheduled, subject)
            confirm.assert_not_called()
        self.assertIsNotNone(db.row('SELECT id FROM subjects WHERE id=?', (scheduled,)))
        self.assertIn('linked to', win.msg.text())
        win.close()

    def test_sample_cleanup_keeps_real_records(self):
        count = db.sample_count()
        self.assertGreater(count, 0)
        with db.conn:
            db.conn.execute(
                "INSERT INTO faculty(name,department,max_units) VALUES('Real Faculty','CCS',18)"
            )
        removed = db.clear_sample_data()
        self.assertEqual(removed, count)
        self.assertEqual(db.sample_count(), 0)
        self.assertIsNotNone(db.row("SELECT id FROM faculty WHERE name='Real Faculty'"))
        self.assertEqual(db.row("SELECT COUNT(*) FROM schedules")[0], 0)
        self.assertEqual(db.row("SELECT COUNT(*) FROM subjects")[0], 0)

    def test_sample_cleanup_refuses_edits_and_new_dependencies(self):
        subject = db.row("SELECT id FROM subjects LIMIT 1")["id"]
        with db.conn:
            db.conn.execute("UPDATE subjects SET title='Our Real Curriculum' WHERE id=?", (subject,))
        before = db.row("SELECT COUNT(*) FROM subjects")[0]
        with self.assertRaisesRegex(ValueError, 'edited'):
            db.clear_sample_data()
        self.assertEqual(db.row("SELECT COUNT(*) FROM subjects")[0], before)

        db.conn.close()
        db.init(':memory:'); db.seed(); auth.init(); init_availability()
        original = db.sample_count()
        with db.conn:
            program = db.row("SELECT id FROM programs WHERE code='BSCS'")["id"]
            db.conn.execute("INSERT INTO sections(name,program_id,enrollment) VALUES('Real 5A',?,30)",
                            (program,))
        with self.assertRaisesRegex(ValueError, 'linked'):
            db.clear_sample_data()
        self.assertEqual(db.sample_count(), original)
        self.assertIsNotNone(db.row("SELECT id FROM sections WHERE name='Real 5A'"))

    def test_sample_tags_survive_reopening_database(self):
        db.conn.close()
        with tempfile.TemporaryDirectory() as directory:
            database_file = os.path.join(directory, 'sample-test.db')
            db.init(database_file)
            db.seed()
            original = db.sample_count()
            db.conn.close()
            db.init(database_file)
            self.assertEqual(db.sample_count(), original)
            self.assertEqual(db.clear_sample_data(), original)
            self.assertEqual(db.sample_count(), 0)
            db.conn.close()
        db.init(':memory:')

    def test_exports_and_auth_disk_persistence(self):
        win=MainWindow(); reports=win.pages['reports']; reports.refresh()
        with tempfile.TemporaryDirectory() as directory:
            pdf=os.path.join(directory,'report.pdf')
            excel_path=os.path.join(directory,'schedule.xlsx')
            reports.report.setCurrentText('Room Utilization Schedule')
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

    def test_schedule_report_filters_support_all_and_individual_choices(self):
        win=MainWindow()
        reports=win.pages['reports']
        reports.refresh()
        for report_name in ('Class Schedules', 'Faculty Schedules', 'Section Schedules'):
            reports.report.setCurrentText(report_name)
            self.assertIsNone(reports.program.currentData())
            self.assertIsNone(reports.section.currentData())
            self.assertIsNone(reports.faculty.currentData())
            self.assertEqual(reports.program.itemText(0), 'All programs')
            self.assertEqual(reports.section.itemText(0), 'All sections')
            self.assertEqual(reports.faculty.itemText(0), 'All faculty')
        reports.report.setCurrentText('Room Utilization Schedule')
        self.assertEqual(reports.program.currentText(), 'All programs')
        self.assertEqual(reports.section.currentText(), 'All sections')
        self.assertEqual(reports.faculty.currentText(), 'All faculty')
        self.assertTrue(all(not combo.isEnabled() for combo in (
            reports.program, reports.section, reports.faculty
        )))
        self.assertTrue(all(reports.room.itemData(i) is not None
                            for i in range(reports.room.count())))
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
