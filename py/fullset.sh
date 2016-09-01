#
# Copyright (c) 2016 the authors of the https://github.com/publicdocs project.
# Use of this file is subject to the NOTICE file in the root of the repository.
#

set -euv

USCCOREVER=102

USCBRANCH=b$USCCOREVER-$USCNUM-rp-$USCRP1-$USCRP2

echo =========================================================================
echo =========================================================================
echo =
echo             !!!!!!! STARTING $USCBRANCH
echo =========================================================================
echo =========================================================================

if [ "$USCSTEP" = "" ]; then
  USCSTEP=01
fi

if [ "$USCSTEP" = "01" ]; then
  USCSTEP=02
  pushd ../uscode-software

  echo To run:
  echo python py/process_xml.py --i=/Users/dev1/Downloads/xml_uscAll\@$USCRP1-$USCRP2.zip --rp1=$USCRP1 --rp2=$USCRP2 --o=../uscode/ --notice=NOTICE --title $USCTITLES
  time python py/process_xml.py --i=/Users/dev1/Downloads/xml_uscAll\@$USCRP1-$USCRP2.zip --rp1=$USCRP1 --rp2=$USCRP2 --o=../uscode/ --notice=NOTICE --title $USCTITLES

  popd
fi


if [ "$USCSTEP" = "02" ]; then
  pushd ../uscode

  git checkout master
  git reset --hard HEAD

  git checkout -b $USCBRANCH

  USCTITLES="$USCTITLES" USCFAILEDTITLES="$USCFAILEDTITLES" sh ../uscode-software/py/update-repo.sh

  git push --set-upstream origin $USCBRANCH

  git tag t-$USCBRANCH

  git branch -f master HEAD ; git push --all ; git push --tags


  popd
  USCSTEP=03
fi


echo =========================================================================
echo =========================================================================
echo =
echo             !!!!!!! FINISHED $USCBRANCH
echo =========================================================================
echo =========================================================================
