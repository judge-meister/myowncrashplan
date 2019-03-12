    @unittest.skip('method moved to another module')
    @patch('os.unlink')
    @patch('myowncrashplan.Settings.verify')
    def test_settings_remove_excl_file_1(self, mock_verify, mock_unlink):
        """verify removal of excl file logs an info when the file does not exist"""
        jstr = """{"debug-level": false}"""
        settings = Settings(jstr, self.log)
        self.assertDictEqual(settings.settings, {"debug-level": False})
        settings.remove_excl_file()
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'rsync exclusions file does not exist.')

    @unittest.skip('method moved to another module')
    @patch('myowncrashplan.Settings.verify')
    def test_settings_remove_excl_file_2(self, mock_verify):
        """verify that rsync_excl file in correctly removed."""
        jstr = """{"rsync-exclude-file": "test.excl"}"""
        with open('test.excl', 'w') as fp:
            fp.write('{}')
        settings = Settings(jstr, self.log)
        self.assertDictEqual(settings.settings, {"rsync-exclude-file": "test.excl"})
        settings.remove_excl_file()
        self.assertNotEqual(os.path.exists('test.excl'), True)
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'rsync exclusions file removed.')

    @unittest.skip('method moved to another module')
    @patch('myowncrashplan.Settings.verify')
    def test_settings_create_excl_file_1(self, mock_verify):
        """verify rsync_excl fie is  created."""
        jstr = """{"rsync-exclude-file": "test.excl",
                   "rsync-excludes-folders": "1,2,3",
                   "debug-level": false
               }"""
        settings = Settings(jstr, self.log)
        self.assertDictEqual(settings.settings, {"rsync-exclude-file": "test.excl", "rsync-excludes-folders": "1,2,3", "debug-level": False})
        settings.set('rsync-excludes-list', settings('rsync-excludes-folders').split(','))
        settings.create_excl_file()
        self.assertTrue(os.path.exists("test.excl"))
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'rsync exclusions file created at test.excl')
        with open("test.excl", 'r') as fp:
            self.assertEqual(fp.read(), "1\n2\n3")
        os.unlink("test.excl")

    @unittest.skip('method moved to another module')
    @patch('myowncrashplan.Settings.verify')
    def test_settings_create_excl_file_2(self, mock_verify):
        """verify creation of rsync_excl file with debug logged."""
        jstr = """{"rsync-exclude-file": "test.excl",
                   "rsync-excludes-folders": "1,2,3",
                   "debug-level": false
               }"""
        settings = Settings(jstr, self.log)
        self.assertDictEqual(settings.settings, {"rsync-exclude-file": "test.excl", "rsync-excludes-folders": "1,2,3", "debug-level": False})
        settings.set('rsync-excludes-list', settings('rsync-excludes-folders').split(','))
        settings.set("debug-level", True)
        settings.create_excl_file()
        self.assertTrue(os.path.exists("test.excl"))
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'rsync exclusions file created at test.excl')
        self.assertEqual(self.log.getVal('debug').split('|')[0], "create_rsync_excl() - EXCLUDES = \n['1', '2', '3']")
        self.assertEqual(self.log.getVal('debug').split('|')[1], 'create_rsync_excl() - test.excl exists True')
        os.unlink("test.excl")
