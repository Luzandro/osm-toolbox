#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

class ProgressBar():
    def __init__(self, message=None):
        self.percentage = 0
        if message:
            print(message)
    
    def update(self, new_percentage):
        new_percentage = round(new_percentage, 2)
        if new_percentage != self.percentage:
            sys.stdout.write("\r{} %   ".format(str(new_percentage).ljust(6)))
            sys.stdout.write('[{}]'.format(('#' * int(new_percentage / 2)).ljust(50)))
            sys.stdout.flush()
        self.percentage = new_percentage

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.update(100)
        sys.stdout.write("\n")