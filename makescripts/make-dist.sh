#!/bin/sh

cd ..

rm -r a3p
mkdir a3p

cp -r maps a3p
cp -r sounds a3p
cp -r models a3p
cp -r images a3p
cp -r menu a3p
cp -r src a3p
cp main.py a3p
cp editor.py a3p

cd a3p
find . -type f -name *.svn -print | xargs -I % rm -r %
find . -type f -name *.svg -print | xargs -I % rm -r %
find . -type f -name *.blend -print | xargs -I % rm -r %
find . -type f -name *.blend1 -print | xargs -I % rm -r %
find . -type f -name *.xcf -print | xargs -I % rm -r %
find . -type f -name *.psd -print | xargs -I % rm -r %
find . -type f -name src-* -print | xargs -I % rm -r %
find . -type f -name *.mtl -print | xargs -I % rm -r %
find . -type f -name *.obj -print | xargs -I % rm -r %
find . -type f -name *.vmf -print | xargs -I % rm -r %
find . -type f -name *.bsp -print | xargs -I % rm -r %
find . -type f -name *.pyc -print | xargs -I % rm -r %
find . -type f -name Thumbs.db -print | xargs -I % rm -r %
cd ..

cp "MIT License.txt" a3p/license.txt

cp web/icon.ico a3p

cd makescripts
