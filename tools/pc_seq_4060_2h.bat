@echo off
rem Double-click: 2-hour judge trial on the RTX 4060 PC (user 11-01).
rem Same as typing in a command window:  pc_seq_4060.bat 2 0 yield j1_4060
rem 2 = hours this sitting, 0 = plan equals this sitting (all four resolution stages within 2 hours),
rem yield = pause/slow down while games run, j1_4060 = new Drive folder seq/j1_4060 (starts fresh, does not resume s1_4060).
rem Keep this file in the same folder as pc_seq_4060.bat.
call "%~dp0pc_seq_4060.bat" 2 0 yield j1_4060
