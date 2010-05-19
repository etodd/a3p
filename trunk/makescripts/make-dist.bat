cd ..

rmdir /S /Q a3p

xcopy maps a3p\maps\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy sounds a3p\sounds\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy models a3p\models\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy images a3p\images\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy src a3p\src\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy menu a3p\menu\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

copy main.py a3p\

copy editor.py a3p\

copy "MIT License.txt" a3p\license.txt

copy web\icon.ico a3p\

cd makescripts