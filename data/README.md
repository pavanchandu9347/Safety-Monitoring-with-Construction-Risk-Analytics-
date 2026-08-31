# Dataset Directory

This directory holds construction dataset / video inputs for the platform.

## Directory structure

```
data/
├── raw/          # Put your construction dataset / videos / images here
├── processed/    # Frame-extracted and preprocessed outputs
├── demo/         # Demo / simulated sample inputs for immediate testing
└── README.md     # This file
```

## Input strategy

Because there is no physical construction site attached to this project, the
system consumes **pre-recorded construction images/videos** as its primary
input, combined with **simulated environmental and equipment monitoring data**.

This is clearly labelled throughout the UI and code as:

**Demo / Simulated Site Monitoring**

## Recommended dataset

For construction computer vision the project references the **CSOD-24**
construction-site video dataset (contains construction-site clips of workers,
excavators, dump trucks, etc.). The object detector used is a YOLO model with
COCO classes (person, truck, car, etc.).

### Auto-label of source

The dataset selection is documented only; it is **not bundled** with this
repository due to licensing / access restrictions. The platform is built so it
can ingest the CSOD-24 clips (or any construction imagery) without redesign of
the Site Risk Agent.

## Where to place the dataset

1. Download the dataset / video clips you wish to use.
2. Place video files (`.mp4`, `.avi`, `.mov`) and/or image files (`.jpg`,
   `.png`) into `data/raw/`.
3. The system and dataset adapter will pick these up. Images can be uploaded
   directly through the frontend **Dataset / Video** page.

## Demo inputs

`data/demo/` may contain small test images used to exercise the computer vision
pipeline. If no images are present, the video page will accept uploads of any
image for analysis.

## Important

Do **not** invent dataset files that do not exist. The pipeline handles missing
inputs gracefully and reports an appropriate message rather than crashing.
