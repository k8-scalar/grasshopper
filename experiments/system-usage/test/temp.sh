# # 3) Setting up grasshopper
# echo "----------- Running GrassHopper as a background process ----------"
# # ensuring the virtual environment is activated.
# source ~/grasshopper-operator/kube_venv/bin/activate
# echo "Environment variables:" >> debug.log
# env >> debug.log
# python3 ../../grasshopper/grasshopper-code/code/main.py --mode PLS --namespace thesis-test > grasshopper.log 2>&1 &
