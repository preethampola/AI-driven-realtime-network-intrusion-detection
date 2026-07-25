# Real-Time Network Intrusion Detection System

An educational intrusion-detection system built with CIC-IDS2017 flow data. It trains binary and multiclass machine-learning models, then scores completed network flows captured by CICFlowMeter and displays results in a Streamlit dashboard.

## What it detects

The deployed multiclass Random Forest predicts six **known** traffic categories:

- `Benign`
- `BruteForce`
- `DDoS`
- `DoS`
- `OtherAttack` (Bot, Infiltration, Heartbleed, and Web Attack grouped together)
- `PortScan`

The Random Forest achieved **99.58% accuracy** and **99.16% macro F1** on a stratified held-out test split. The notebook also compares an MLP neural network, which achieved **98.50% accuracy** and **97.33% macro F1**. These are known-category test results: each category occurs in both training and test data; they should not be treated as performance on unknown attacks.

## Repository layout

```text
notebooks/                         Reproducible training and evaluation notebooks
models/                            Included trained models for immediate use
app.py                             Streamlit dashboard
watch_live_flows.py                Watches new CICFlowMeter CSV flow rows
ids_scoring.py                     Shared feature alignment and inference logic
```

## Quick start

This repository includes the deployed multiclass Random Forest model, so you can run the dashboard without retraining.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run .\app.py
```

## Reproducing the training results

### 1. Install prerequisites

- Python **3.12** (recommended)
- Git, only if you are cloning the repository from GitHub
- The packages in `requirements.txt`

Create an environment and install the dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Download and place the dataset

Download **MachineLearningCSV.zip** from the official [CIC-IDS2017 dataset page](https://www.unb.ca/cic/datasets/ids-2017.html). Extract its CSV files below this repository as follows:

```text
Realtime-IDS-GitHub/
└── data/
    └── cicids2017/
        ├── Monday-WorkingHours.pcap_ISCX.csv
        ├── Tuesday-WorkingHours.pcap_ISCX.csv
        ├── Wednesday-workingHours.pcap_ISCX.csv
        └── ...other extracted CIC-IDS2017 CSV files
```

The notebooks recursively locate CSV files, so an extra extracted subfolder inside `data/cicids2017/` is also acceptable.

### 3. Run the notebooks

Open the repository folder in VS Code, select the `.venv` Python 3.12 kernel, and run each notebook from top to bottom:

- `notebooks/binary_ids_analysis.ipynb` trains and compares binary Random Forest and MLP models.
- `notebooks/multiclass_ids_analysis.ipynb` trains and compares six-category Random Forest and MLP models.

Both notebooks use a fixed random seed and a stratified held-out split. Random Forest results should reproduce closely; neural-network results can vary slightly across TensorFlow/hardware versions.

## Near-live flow monitoring

For authorised monitoring on a machine you own, use CICFlowMeter to capture an active network adapter. Then start the watcher:

```powershell
python .\watch_live_flows.py --capture-dir "C:\path\to\CICFlowMeter\data\daily"
```

Keep the Streamlit dashboard and watcher running. CICFlowMeter writes completed-flow rows; the watcher scores only newly added rows and the dashboard refreshes the results. This is flow-level, near-live detection—not per-packet inspection.

For this optional live-monitoring extension, you must install and run CICFlowMeter separately. On Windows its packet-capture dependency (such as Npcap) must also be installed. Neither tool is required to reproduce the training notebooks or to open the dashboard.

### Optional: Run CICFlowMeter on Windows

The following instructions describe the Windows setup used for this project. CICFlowMeter is a separate Java application; it captures network packets and writes completed network flows as CSV rows.

1. Install **Npcap** and confirm that its packet-capture driver is running.
2. Install a Java 8 JDK. The legacy CICFlowMeter Gradle build used here is not compatible with newer Java releases such as Java 21.
3. Download or clone CICFlowMeter outside this repository. If its legacy Windows build requires a local `jnetpcap` dependency, follow that tool's Windows setup instructions before building.
4. Open PowerShell and launch CICFlowMeter. Replace the two example paths with your own paths:

```powershell
$env:JAVA_HOME = "C:\Program Files\Java\jdk1.8.0_491"
$env:Path = "$env:JAVA_HOME\bin;$env:Path"

Set-Location "C:\Project\CICFlowMeter-master"
.\gradlew.bat run
```

In the CICFlowMeter window, click **Load**, select the active network adapter (for example, Wi-Fi), then click **Start**. It writes flow files under its `data\daily\` directory.

In a second PowerShell window, start this project's watcher and dashboard:

```powershell
Set-Location "C:\path\to\Realtime-IDS-GitHub"
.\.venv\Scripts\Activate.ps1

python .\watch_live_flows.py --capture-dir "C:\Project\CICFlowMeter-master\data\daily"
```

In a third PowerShell window, start the dashboard:

```powershell
Set-Location "C:\path\to\Realtime-IDS-GitHub"
.\.venv\Scripts\Activate.ps1
python -m streamlit run .\app.py
```

Keep all three programs running while monitoring: CICFlowMeter captures flows, the watcher scores newly completed rows, and Streamlit displays the predictions.

## Responsible use

Use this project only on systems and networks you own or are explicitly authorised to monitor. It is an academic prototype that flags flows for human review; it is not a replacement for a production security platform.
