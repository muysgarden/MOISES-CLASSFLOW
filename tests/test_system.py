import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
import tempfile
from PyQt5.QtWidgets import QApplication, QFrame
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
import db
import auth
import logic
from ui.availability import init_availability, unavailable
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
        combo=page.form.widgets['name']
        self.assertEqual(combo.currentText(), '')
        combo.setCurrentIndex(1)
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
