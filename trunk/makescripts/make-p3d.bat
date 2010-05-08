cd ..

call makescripts/paths.bat
panda3d makescripts/packp3d.p3d -o pkg/game.p3d -S makescripts/certificate.pem -d p3d-src -c script_origin=a3p.sourceforge.net -r ode,cmu_1.7 -r fmod,cmu_1.7 -r morepy,cmu_1.7 -r a3pimages,,http://a3p.sourceforge.net/a3pimages -r a3pmaps,,http://a3p.sourceforge.net/maps -r a3pmodels,,http://a3p.sourceforge.net/models -r a3psounds,,http://a3p.sourceforge.net/sounds

panda3d makescripts/packp3d.p3d -o pkg/install.p3d -S makescripts/certificate.pem -d p3d-src -m install.py -c script_origin=a3p.sourceforge.net -r ode,cmu_1.7 -r fmod,cmu_1.7 -r morepy,cmu_1.7 -r a3pimages,,http://a3p.sourceforge.net/a3pimages -r a3pmaps,,http://a3p.sourceforge.net/maps -r a3pmodels,,http://a3p.sourceforge.net/models -r a3psounds,,http://a3p.sourceforge.net/sounds

cd makescripts