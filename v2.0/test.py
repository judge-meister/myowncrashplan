#!/usr/bin/env python

import unittest

from TestRsyncMethod import TestRsyncMethod
from TestSettings    import TestSettings
from TestRemoteComms import TestRemoteComms
from TestMetaData    import TestMetaData
from TestCrashPlan   import TestCrashPlan

#with patch("builtins.open", mock_open(read_data="data")) as mock_file:
#    assert open("path/to/open").read() == "data"
#    mock_file.assert_called_with("path/to/open")
#[call('/Users/judge/.metadata', 'w'),
# call().__enter__(),
# call().write('{"backup-today": "2019-01-02", "latest-complate": "2019-01-02-012345", "latest-complete": ""}\n'),
# call().__exit__(None, None, None)]


if __name__ == '__main__':
    
    unittest.main(verbosity=1)