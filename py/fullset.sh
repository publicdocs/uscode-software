#!/bin/bash
#
# Copyright (c) 2016 the authors of the https://github.com/publicdocs project.
# Use of this file is subject to the NOTICE file in the root of the repository.
#

set -euv

USCCOREVER=301

USCBRANCH=v$USCCOREVER-$USCNUM-rp-$USCRP1-$USCRP2

echo =========================================================================
echo =========================================================================
echo =
echo             !!!!!!! STARTING $USCBRANCH
echo =========================================================================
echo =========================================================================

if [ "$USCSTEP" = "" ]; then
  USCSTEP=00
fi

USCFN=xml_uscAll\@${USCRP1}-${USCRP2}.zip


if [ "$USCSTEP" = "00" ]; then
  mkdir -p ../Downloads/ ../uscode/assets/md/titles/

  USCSTEP=01
  if [ -e ../Downloads/$USCFN ] ; then
    echo STEP 0 - Already have http://uscode.house.gov/download/releasepoints/us/pl/$USCRP1/$USCRP2/$USCFN
  else
    echo STEP 0 - Downloading http://uscode.house.gov/download/releasepoints/us/pl/$USCRP1/$USCRP2/$USCFN
    # As of 2016-Sep-1, http://uscode.house.gov/robots.txt only disallows the 'Slurp' bot,
    # but doesn't block other bots.  Regardless, let's be curteous.
    curl -A "$PROC_UA" http://uscode.house.gov/robots.txt > ../Downloads/robots.txt
    if grep -q "$PROC_UA_PART" "../Downloads/robots.txt"; then
      echo The following robots.txt was found and it contains $PROC_UA_PART :
      cat ../Downloads/robots.txt
      # This will cause the script to fail since the environment variable doesn't exist.
      echo $PROC_UA_FAIL_CANNOT_CONTINUE
      exit -1
    fi
    curl -A "$PROC_UA" http://uscode.house.gov/download/releasepoints/us/pl/$USCRP1/$USCRP2/$USCFN > ../Downloads/$USCFN
  fi
fi

if [ "$USCSTEP" = "01" ]; then
  USCSTEP=02
  pushd ../uscode-software

  echo To run:
  echo python py/process_xml.py --i=../Downloads/$USCFN --rp1=$USCRP1 --rp2=$USCRP2 --o=../uscode/ --notice=NOTICE --title $USCTITLES
  time python py/process_xml.py --i=../Downloads/$USCFN --rp1=$USCRP1 --rp2=$USCRP2 --o=../uscode/ --notice=NOTICE --title $USCTITLES

  popd
fi


if [ "$USCSTEP" = "02" ]; then
  pushd ../uscode

  git checkout master
  git reset --hard HEAD

  git checkout -b $USCBRANCH || ( git branch -D $USCBRANCH && git checkout -b $USCBRANCH )
  git reset --hard master

  USCTITLES="$USCTITLES" USCFAILEDTITLES="$USCFAILEDTITLES" sh ../uscode-software/py/update-repo.sh

  echo 24i >_t.ed
  echo - [Release Point at PL $USCRP1-$USCRP2]\(https://github.com/publicdocs/uscode/tree/t-$USCBRANCH\) >>_t.ed
  echo . >>_t.ed
  echo w >>_t.ed
  echo q >>_t.ed
  ed README.md <_t.ed
  rm _t.ed
  popd
  USCSTEP=03
fi

if [ "$USCSTEP" = "03" ]; then
  pushd ../uscode

  USC_SW_VER=$(git --git-dir=../uscode-software/.git rev-parse HEAD)

  git add -A .
  git commit -m "U.S.C. (Public Docs Rel $USCRP1-$USCRP2)

  All valid titles updated.

  Generated with https://github.com/publicdocs/uscode-software/tree/$USC_SW_VER"

  popd
  USCSTEP=04
fi


if [ "$USCSTEP" = "04" ]; then
  pushd ../uscode

  git push -f --set-upstream origin $USCBRANCH

  git tag -f t-$USCBRANCH

  git branch -f master HEAD ; git push -f --all ; git push --tags -f

  popd
  USCSTEP=05
fi


echo =========================================================================
echo =========================================================================
echo =
echo             !!!!!!! FINISHED $USCBRANCH
echo =========================================================================
echo =========================================================================
