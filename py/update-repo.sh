#!/bin/bash
#
# Copyright (c) 2016 the authors of the https://github.com/publicdocs project.
# Use of this file is subject to the NOTICE file in the root of the repository.
#

USC_SW_VER=$(git --git-dir=../uscode-software/.git rev-parse HEAD)



# for each title:

USCALLTITLES="01 02 03 04 05 05A 06 07 08 09 10 11 11A 12 13 14 15 16 17 18 18A 19 20 21 22 23 24 25 26 27 28 28A 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 50A 51 52 53 54 55 56 57 58 59 60"
USCCURTITLES="$USCTITLES"
if [ -z "$USCCURTITLES" ]; then
    USCCURTITLES="$USCALLTITLES"
fi


for USCNUM in $USCFAILEDTITLES
do
  if [ -e assets/md/titles/usc$USCNUM/us ] ; then
    echo P0 Report corrupt file $USCNUM
    sed -i -e "s/ Release Point:/ __WARNING: XML file could not be parsed at Release Point $USCRP1-$USCRP2,__ therefore this Title remains at Release Point:/g" assets/md/titles/usc$USCNUM/README.md
    # sed leaves a file.
    rm assets/md/titles/usc$USCNUM/README.md-e
  else
    echo P0 No such title $USCNUM
  fi
done

git add -A .
git commit -m "Rel $USCRP1-$USCRP2 - Corrupted USC titles: $USCFAILEDTITLES

These titles cannot be updated, usually because their XML files are invalid or corrupted, and remain at the prior release point.

Generated with https://github.com/publicdocs/uscode-software/tree/$USC_SW_VER" || echo P0 No corrupt files.


USCMDONLY=" "
for USCNUM in $USCCURTITLES
do
  if [ -e assets/md/titles/usc$USCNUM/us ] || [ -e ../uscode-software/working/gen/titles/usc$USCNUM/us ] ; then
    git diff --exit-code --quiet --no-index assets/md/titles/usc$USCNUM/us ../uscode-software/working/gen/titles/usc$USCNUM/us
    if [ $? -eq 0 ] ; then
      echo P1 Skipping $USCNUM for now - no content difference.
      USCMDONLY="$USCMDONLY $USCNUM"
    else
      rm -rf assets/md/titles/usc$USCNUM
      mkdir assets/md/titles/usc$USCNUM
      cp -R ../uscode-software/working/gen/titles/usc$USCNUM assets/md/titles
      git add -A .
      USCDIFFSTAT=$(git diff --shortstat HEAD | sed -e 's/ changed//g' | sed -e 's/insertions//g' | sed -e 's/insertion//g' | sed -e 's/deletions//g' | sed -e 's/deletion//g' | tr '\n' ' ')
      if [ "z-$USCDIFFSTAT-z" = 'z- 2 files, 7 (+), 7 (-)-z' ]; then
        echo P1 Minor Content difference for $USCNUM - skipping until end.
        git reset --hard HEAD
        USCMDONLY="$USCMDONLY $USCNUM"
      else
        echo P1 Major Content difference for $USCNUM - committing.
        git commit -m "Rel $USCRP1-$USCRP2 - USC $USCNUM :$USCDIFFSTAT

Generated with https://github.com/publicdocs/uscode-software/tree/$USC_SW_VER"
      fi
    fi
  else
    echo P1 No such title $USCNUM
  fi
done

for USCNUM in $USCMDONLY
do
  if [ -e assets/md/titles/usc$USCNUM/us ] || [ -e ../uscode-software/working/gen/titles/usc$USCNUM/us ] ; then
    echo P2 Metadata update $USCNUM
    rm -rf assets/md/titles/usc$USCNUM
    mkdir assets/md/titles/usc$USCNUM
    cp -R ../uscode-software/working/gen/titles/usc$USCNUM assets/md/titles
  else
    echo P2 No such title $USCNUM
  fi
done


git add -A .
git commit -m "Rel $USCRP1-$USCRP2 - USC titles with metadata update only: $USCMDONLY

Generated with https://github.com/publicdocs/uscode-software/tree/$USC_SW_VER" || echo P2 No metadata only titles.
