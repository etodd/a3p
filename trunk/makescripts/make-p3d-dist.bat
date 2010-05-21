cd ..

rmdir /S /Q a3p-pkg
rmdir /S /Q a3p-src

xcopy maps a3p-pkg\maps\ /i /e /y /exclude:makescripts\multifile-exclusions.txt
xcopy sounds a3p-pkg\sounds\ /i /e /y /exclude:makescripts\multifile-exclusions.txt
xcopy models a3p-pkg\models\ /i /e /y /exclude:makescripts\multifile-exclusions.txt
xcopy images a3p-pkg\images\ /i /e /y /exclude:makescripts\multifile-exclusions.txt
xcopy menu a3p-pkg\menu\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy src a3p-src\src\ /i /e /y /exclude:makescripts\multifile-exclusions.txt
copy main.py a3p-src\

cd makescripts