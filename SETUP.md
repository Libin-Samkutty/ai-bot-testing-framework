# Setup Guide

This guide walks you through the initial setup of the AI Bot Testing Framework.

## Prerequisites

- Python 3.8+
- An OpenAI API key (get one at https://platform.openai.com/account/api-keys)
- ~5 minutes

## Step 1: Clone or Download the Repository

```bash
git clone <repository-url>
cd ai-bot-testing-framework
```

## Step 2: Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 4: Configure Your API Key

### Option A: Using config.example.yaml (Recommended)

This ensures your API key is never accidentally committed to version control.

```bash
cp config.example.yaml config.yaml
```

Then edit `config.yaml`:
```yaml
openai:
  api_key: "sk-proj-your-actual-key-here"  # ← Replace this!
  judge_model: "gpt-4o-mini"
```

### Option B: Manual Setup

If you already have a `config.yaml`, just update the `api_key` field.

## Step 5: Verify Your Setup

Run a dry-run to validate everything without cost:

```bash
python run_eval.py --csv test_cases/sample.csv --dry-run
```

You should see:
```
✅  Validation passed — ready to run:
    python run_eval.py --csv test_cases/sample.csv
```

## Step 6: Try Your First Evaluation

```bash
python run_eval.py --csv test_cases/sample.csv
```

This will:
1. Test a demo bot with 19 sample questions
2. Evaluate each answer with AI judges
3. Generate an HTML report in `outputs/report_<timestamp>.html`

## Step 7: Try the Diabetes Bot Demo

```bash
python run_diabetes_demo.py --csv test_cases/diabetes_tests.csv --dry-run
python run_diabetes_demo.py --csv test_cases/diabetes_tests.csv
```

---

## Configuration Reference

### config.yaml Structure

| Section | Key | Purpose |
|---------|-----|---------|
| `openai` | `api_key` | Your OpenAI API key (keep this secret!) |
| `openai` | `judge_model` | Which model to use for evaluation (gpt-4o-mini, gpt-4o, etc.) |
| `evaluation` | `temperature` | Randomness (0.0 = deterministic, recommended) |
| `evaluation` | `max_tokens` | Max response length (512 is usually enough) |
| `output` | `reports_dir` | Where to save reports (default: outputs) |
| `pricing` | `<model>` | Token prices in USD per 1M tokens |

### Why Not Track config.yaml?

The `config.yaml` file contains your API key and is in `.gitignore` to protect it. If you accidentally commit it, your key could be exposed. Always use `config.example.yaml` as a template instead.

---

## Security Best Practices

1. **Never commit `config.yaml`** — it's in .gitignore for your protection
2. **Rotate your API key** if you accidentally expose it
3. **Use environment-specific configs** if running in multiple environments
4. **Keep your API key private** — treat it like a password

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'openai'"

Your virtual environment isn't activated. Run:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### "API key error" or "Authentication failed"

- Check your `config.yaml` file exists and is in the same directory as the scripts
- Verify your API key is correct in `config.yaml`
- Ensure your OpenAI account has credits/balance
- Don't include quotes around the API key if you copy-paste it

### "config.yaml not found"

You need to create it from the template:
```bash
cp config.example.yaml config.yaml
# Then edit config.yaml and add your API key
```

### "CSV file not found"

The test cases should be in `test_cases/` directory. Check:
```bash
ls -la test_cases/
```

---

## Next Steps

- Read the [README.md](README.md) for detailed usage examples
- Check out the [Diabetes Bot Demo](README.md#-diabetes-bot-demo) to understand how to test your own bot
- Create your own test cases in CSV format
- Explore custom evaluators in the `plugins/` directory

---

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Run `--dry-run` to validate your setup
3. Check the error message carefully — it usually tells you what's wrong
4. See the README.md [Troubleshooting](README.md#troubleshooting) section for more help
