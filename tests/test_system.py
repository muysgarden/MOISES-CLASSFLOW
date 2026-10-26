import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
import tempfile
from PyQt5.QtWidgets import QApplication
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
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
        page.save()
        self.assertEqual(db.row('SELECT COUNT(*) FROM schedules')[0],before+1)
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
            pdf=directory+'/report.pdf'; csv_path=directory+'/report.csv'
            with patch('ui.reports.QFileDialog.getSaveFileName',return_value=(pdf,'PDF')): reports.export_pdf()
            with patch('ui.reports.QFileDialog.getSaveFileName',return_value=(csv_path,'CSV')): reports.export_csv()
            self.assertGreater(os.path.getsize(pdf),1000)
            with open(csv_path,encoding='utf-8-sig') as f: self.assertIn('Subject,Section,Faculty,Room,Day,Time',f.read())
        win.close()
        db.conn.close()
        with tempfile.TemporaryDirectory() as directory:
            path=directory+'/test.db'; db.init(path); auth.init(); auth.create('admin','persistent-password'); db.conn.close()
            db.init(path); auth.init(); self.assertTrue(auth.verify('admin','persistent-password')); db.conn.close()
        db.init(':memory:')
        # tearDown closes the connection.

    def test_all_pages_and_report(self):
        win=MainWindow(); win.show(); app.processEvents()
        for key in win.pages:
            win.go(key); app.processEvents(); self.assertEqual(win.stack.currentWidget(),win.pages[key])
        reports=win.pages['reports']
        for i in range(reports.report.count()):
            reports.report.setCurrentIndex(i); app.processEvents(); self.assertTrue(reports.headers)
        reports.report.setCurrentIndex(2)
        printer=QPrinter(); printer.setOutputFormat(QPrinter.PdfFormat); printer.setOutputFileName(os.path.join(tempfile.gettempdir(),'classflow-report-test.pdf')); reports.document().print_(printer)
        self.assertGreater(os.path.getsize(os.path.join(tempfile.gettempdir(),'classflow-report-test.pdf')),1000)
        # Capture each actual UI for visual inspection.
        for key in win.pages:
            win.go(key); app.processEvents(); win.grab().save(os.path.join(tempfile.gettempdir(),'classflow-'+key+'.png'))
        win.close()


if __name__=='__main__': unittest.main()
