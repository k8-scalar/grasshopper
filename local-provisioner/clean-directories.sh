for i in 31 32 34 35 36 37 38 39
do 
	ssh -t ubuntu@172.17.124.$i "sudo rm -r  /data-pvg/1/*; sudo rm -r  /data-pvg/2/*; sudo rm -r  /data-pvg/3/*; sudo rm -r  /data-pvg/4/*; sudo rm -r  /data-pvg/5/*"
	
done
