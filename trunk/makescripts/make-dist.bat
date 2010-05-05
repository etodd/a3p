cd ..

rmdir /S /Q pkg-maps
rmdir /S /Q pkg-sounds
rmdir /S /Q pkg-models
rmdir /S /Q pkg-maps
rmdir /S /Q p3d-src

xcopy maps pkg-maps\maps\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy shaders pkg-shaders\shaders\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy sounds pkg-sounds\sounds\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy models pkg-models\models\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy images pkg-images\images\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

xcopy src p3d-src\src\ /i /e /y /exclude:makescripts\multifile-exclusions.txt

copy main.py p3d-src\

copy install.py p3d-src\

cd makescripts