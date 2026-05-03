
NAME = Ecobee
XML_FILES = profile/*/*.xml 

# sudo apt-get install libxml2-utils libxml2-dev
check:
	echo ${XML_FILES}
	xmllint --noout ${XML_FILES}

# Dev: pip install -r requirements-dev.txt
test:
	python3 -m pytest -q

zip:
	zip -x@zip_exclude.lst -r ${NAME}.zip *
