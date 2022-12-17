for i in 31 32 34 35 36 37 38 39
do 
	ssh ubuntu@172.17.124.$i 'for k in 1 2 3 4 5; do chmod 777 /data-pvg/$k; done'
	
done
