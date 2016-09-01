#
# Copyright (c) 2016 the authors of the https://github.com/publicdocs project.
# Use of this file is subject to the NOTICE file in the root of the repository.
#

set -euv

echo !!!!!!! BUILDING b$USCNUM-rp-$USCRP1-$USCRP2

pushd ../uscode-software

time python py/process_xml.py --i=/Users/dev1/Downloads/xml_uscAll\@$USCRP1-$USCRP2.zip --rp1=$USCRP1 --rp2=$USCRP2 --o=../uscode/ --notice=NOTICE --title $USCTITLES

popd

pushd ../uscode

git checkout master
git reset --hard HEAD

git checkout -b b$USCNUM-rp-$USCRP1-$USCRP2

USCTITLES="$USCTITLES" USCFAILEDTITLES="$USCFAILEDTITLES" sh ../uscode-software/py/update-repo.sh

git push --set-upstream origin b$USCNUM-rp-$USCRP1-$USCRP2

git branch -f master HEAD ; git push --all


popd
