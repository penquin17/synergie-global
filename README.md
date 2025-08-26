# Installation

prerequisite: conda

```bash
cd synergie-global
conda create -y -n synergie python=3.12
conda install -y -n synergie -c conda-forge conda-build cython pip sqlite uv poetry
conda install -y -n synergie -c conda-forge c-compiler cxx-compiler

conda activate synergie
conda run -v -n synergie uv pip install -e ".[develop]"
```

## Information

- Demo Transcript: Available at synergie-global/src/agent/transcript.csv.
- Run Demo: Execute with

  ```bash
  conda activate synergie
  python synergie-global/src/agent/demo.py
  ```

- Features
  - Built with LangChain.
  - Supports asynchronous execution.
  - Produces simple structured outputs.
  - Implements state handling for tool calls, including a fake API to retrieve available service options.

- Room for Improvement
  - Add Pydantic validation for structured outputs.
  - Extend coverage for edge cases.
  - Enhance state management and conversation history tracking (current implementation assumes short and simple conversations).
