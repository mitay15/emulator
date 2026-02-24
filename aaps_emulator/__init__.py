# aaps_emulator package initializer: configure package logger
import logging

# Ensure library users don't get spammed if they don't configure logging.
logging.getLogger("aaps_emulator").addHandler(logging.NullHandler())
