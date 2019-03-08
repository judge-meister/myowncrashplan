# pylint: disable=invalid-name
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines

"""
Small utility classes
"""

import time

class TimeDate():
    """Date and Time object"""
    
    @staticmethod
    def stamp():
        """return a timestamp"""
        return time.strftime("%Y/%m/%d %H:%M:%S")
        
    @staticmethod
    def datedir():
        """return a datedir name"""
        return time.strftime("%Y-%m-%d-%H%M%S")

    @staticmethod
    def today():
        """return a representing todays date"""
        return time.strftime("%Y-%m-%d")

