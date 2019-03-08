# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines

"""
CrashPlanError exception
"""

class CrashPlanError(Exception):
    """crash plan error"""

    def __init__(self, message):
        """init"""
        super().__init__(message)
        self.value = message

    def __str__(self):
        """str"""
        return repr(self.value)

