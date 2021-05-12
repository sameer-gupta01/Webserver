pkill python3

echo "-------------"
echo "Running Tests"
echo "-------------"
echo ""

cd tests

count=1

for t in *.sh;
do
	echo "Running Test $count"
	bash $t
	pkill python3
	count=$((count+1))
done;

cd ..
cd extension_tests

echo ""
echo "-----------------------"
echo "Running Extension Tests"
echo "-----------------------"
echo ""

count=1

for t in *.sh;
do
	echo "Running Test $count"
	bash $t
	pkill python3
	count=$((count+1))
done;
