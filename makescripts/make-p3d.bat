cd ..

call makescripts/paths.bat
panda3d makescripts/packp3d.p3d -o game.p3d -S makescripts/certificate.pem -d a3p-src -c script_origin=a3p.sourceforge.net -r ode,cmu_1.7 -r fmod,cmu_1.7 -r morepy,cmu_1.7 -r pkg,,http://a3p.sourceforge.net
cd makescripts