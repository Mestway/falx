#!/bin/bash

unameOut="$(uname -s)"
case "${unameOut}" in
    Linux*)     timeout_cmd=timeout;;
    Darwin*)    timeout_cmd=gtimeout;;
esac
echo ${timeout_cmd}

dt=$(date '+%Y%m%d_%H%M%S')

dirname="../benchmarks/"
num_samples=3
time_limit=600
###falx | forward | morpheus | none
prune=falx
output_dir="../output/exp_"$prune"_"$num_samples"_"$dt

data_list=(
    #easy noes
    "001" "002" "003" 
    "004" "005" "006" "007" "008" "009" "010" 
    "011" "012" "013" "014" "015" "016" "017" "018" "019" "020" 
    "021" "022" "023" "024" "025" "026" "027" "028" "029" "030" 
    "031" "032" "033" "034" "035" "036" "037" "038" "039" "040" 
    "041" "042" "043" "044" "045" "046" "047" "048" "049" "050" 
    "051" "052" "053" "054" "055" "056" "057" "058" "059" "060"
    "test_1" "test_2" "test_3" "test_4" "test_5" "test_6" "test_7" 
    "test_8" "test_9" "test_10" "test_11" "test_12" "test_13" "test_14" 
    "test_15" "test_16" "test_17" "test_18" "test_19" "test_20" "test_21" 
    "test_22" "test_23"
)


echo "## experiment result in: "$output_dir
echo "## number of sample used: "$num_samples

#gtimeout $time_limit python run.py "--data_id=001" "--num_samples=$num_samples"

mkdir $output_dir
for i in "${data_list[@]}"; do
	echo "# running benchamrk $i"
    { time stdbuf -oL $timeout_cmd $time_limit python run.py --data_id=$i --num_samples=$num_samples --prune=$prune ; } >& "$output_dir/$i.log"
done


