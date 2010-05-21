cd ..

call makescripts/paths.bat
panda3d makescripts/ppackage.p3d -i . -S makescripts/certificate.pem makescripts/pkg.pdef

cd makescripts