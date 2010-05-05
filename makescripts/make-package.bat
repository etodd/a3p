cd ..

call makescripts/paths.bat
panda3d makescripts/ppackage.p3d -i pkg/a3pimages -S makescripts/certificate.pem makescripts/images.pdef
panda3d makescripts/ppackage.p3d -i pkg/maps -S makescripts/certificate.pem makescripts/maps.pdef
panda3d makescripts/ppackage.p3d -i pkg/sounds -S makescripts/certificate.pem makescripts/sounds.pdef
panda3d makescripts/ppackage.p3d -i pkg/shaders -S makescripts/certificate.pem makescripts/shaders.pdef
panda3d makescripts/ppackage.p3d -i pkg/models -S makescripts/certificate.pem makescripts/models.pdef

cd makescripts