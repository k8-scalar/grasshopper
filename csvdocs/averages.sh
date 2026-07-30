GHV_DIR=$PYTHONPATH
RESULTS_DIR=${GHV_DIR}/results/per-labelSet/teastore-gh
printf "\n=========================================\n"

printf "\n=====Deleting earlier files if any ======\n"
cd ${GHV_DIR}/csvdocs/
rm teastore*

printf "\n=====Copying new files to the csvdocs directory ======\n"
cp $RESULTS_DIR/* ${GHV_DIR}csvdocs/

printf "\n=====Converting all .csv files to .xlsx ======\n"
python3 csvtoxlsx.py

printf "\n=====Combining all files and get the average ======\n"
echo
echo
read -p "Which average do you wish to calculate? [Request(R)/Distribution(D)] " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Dd]$ ]]
then
  python3 average_distribution.py;
  printf "\n\n ====DONE====\n"
  echo
  sleep 2
  
  read -p "Do you now wish to calcualate average for Request? [y/n] " -n 1 -r

  if [[ $REPLY =~ ^[Yy]$ ]]
  then
    echo
    python3 average_requests.py;
    sleep 2
    printf "\n\n ====END====\n"
    echo

  else
    printf "==============================\n"
    printf "\n====END====\n"
  fi
  
elif [[ $REPLY =~ ^[Rr]$ ]]
then
  python3 average_requests.py;
  printf "\n\n ====DONE====\n"
  echo
  sleep 2
  read -p "Do you now wish to calcualate average for Distribution? [y/n] " -n 1 -r

  if [[ $REPLY =~ ^[Yy]$ ]]
  then
    echo
    python3 average_distribution.py;
    sleep 2
    printf "\n====END====\n"
    echo

  else
    printf "==============================\n"
    printf "\n====END====\n"
  fi
  
else
  printf "==============================\n"
  printf "\n====Averages not calculated====\n"
fi
