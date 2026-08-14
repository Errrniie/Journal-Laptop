#!/bin/bash
cd /home/LxSparda/Desktop/Journal || exit 1
source .venv/bin/activate
exec -a ernesto-journal python main.py
