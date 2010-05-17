cd ..

rmdir /S /Q dist

xcopy maps dist\maps\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy sounds dist\sounds\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy models dist\models\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy images dist\images\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy src dist\src\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy menu dist\menu\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

copy main.py dist\

copy editor.py dist\

copy "MIT License.txt" dist\license.txt

copy web\icon.ico dist\

cd makescripts