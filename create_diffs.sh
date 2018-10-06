#!/bin/bash
OLD='2017-10-01'
NEW='2018-04-02'
DIFF="DIFF_${OLD}_${NEW}"

cd results/

find $NEW -name "*.osm" -print0 | while read -d $'\0' file
do
    mkdir -p $(dirname ${file/$NEW/$DIFF});
    if [ -f ${file/$NEW/$OLD} ]; then
        # compare nodes and ignore date difference and header/footer
        comm_result=$(comm -13 <(sed s/$OLD/$NEW/g ${file/$NEW/$OLD} | head -n -2 | tail -n +3) <(head -n -2 $file | tail -n +3);)
        if [ "$comm_result" != "" ]
        then
            (head -2 $file; echo $comm_result; tail -3 $file) > ${file/$NEW/$DIFF}
        fi
    else
        cp $file ${file/$NEW/$DIFF}
    fi
done
