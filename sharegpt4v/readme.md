Follow the instructions below to install the dependencies and run the code.

!git clone https://github.com/InternLM/InternLM-XComposer --depth=1
!cd InternLM-XComposer/projects/ShareGPT4V
##!conda create -n share4v python=3.10 -y # create a new environment, or use venv
##!conda activate share4v # activate the environment, or use venv

!pip install --upgrade pip
!pip install -e .
!pip install -e ".[train]"
!pip install flash-attn --no-build-isolation
