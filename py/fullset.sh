#
# Copyright (c) 2016 the authors of the https://github.com/publicdocs project.
# Use of this file is subject to the NOTICE file in the root of the repository.
#

set -euv

USCCOREVER=101

USCBRANCH=b$USCCOREVER-$USCNUM-rp-$USCRP1-$USCRP2
echo !!!!!!! BUILDING $USCBRANCH

pushd ../uscode-software

echo To run:
echo python py/process_xml.py --i=/Users/dev1/Downloads/xml_uscAll\@$USCRP1-$USCRP2.zip --rp1=$USCRP1 --rp2=$USCRP2 --o=../uscode/ --notice=NOTICE --title $USCTITLES
time python py/process_xml.py --i=/Users/dev1/Downloads/xml_uscAll\@$USCRP1-$USCRP2.zip --rp1=$USCRP1 --rp2=$USCRP2 --o=../uscode/ --notice=NOTICE --title $USCTITLES

popd

pushd ../uscode

git checkout master
git reset --hard HEAD

git checkout -b $USCBRANCH

USCTITLES="$USCTITLES" USCFAILEDTITLES="$USCFAILEDTITLES" sh ../uscode-software/py/update-repo.sh

git push --set-upstream origin $USCBRANCH

git tag t-$USCBRANCH

git branch -f master HEAD ; git push --all ; git push --tags


popd
