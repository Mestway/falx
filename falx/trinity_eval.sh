#!/bin/bash

unameOut="$(uname -s)"
case "${unameOut}" in
    Linux*)     timeout_cmd=timeout;;
    Darwin*)    timeout_cmd=gtimeout;;
esac
echo ${timeout_cmd}

dt=$(date '+%Y%m%d_%H%M%S')

dirname="../benchmarks/"
time_limit=600
###falx | forward | morpheus | none
prune=morpheus
output_dir="../output/trinity_exp_"$prune"_"$dt

data_list=(
   "trinity-003" "trinity-004" "trinity-006" "trinity-008"
   "trinity-010" "trinity-014" "trinity-016" "trinity-025"  
   "trinity-040" "trinity-049" "trinity-052" "trinity-053"
)


echo "## experiment result in: "$output_dir

#gtimeout $time_limit python run.py "--data_id=001" "--num_samples=$num_samples"

mkdir $output_dir
for i in "${data_list[@]}"; do
	echo "# running benchamrk $i"
    { time stdbuf -oL $timeout_cmd $time_limit python run.py --data_id=$i --prune=$prune ; } >& "$output_dir/$i.log"
done


