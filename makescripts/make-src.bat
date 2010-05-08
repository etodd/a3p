cd ..

rmdir /S /Q dist-src

xcopy maps dist-src\maps\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy sounds dist-src\sounds\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy models dist-src\models\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy images dist-src\images\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy src dist-src\src\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

copy main.py dist-src\

cd makescripts