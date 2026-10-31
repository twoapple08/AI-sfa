@echo off
rem 학습 준비만(설치, 기본 모델 받기, 자료 풀기). 인물 자르기가 GPU를 쓰는 동안 미리 돌려 둘 수 있음
call "%~dp0pc_lora_train.bat" prep
