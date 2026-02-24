# Requirements Analysis: Lung Cancer Detection Project

## Project Requirements Summary

The project should develop an intelligent system to assist physicians in early diagnosis of lung cancer by:

1. **Analyzing CT/PET scans** and predicting different **tumor biomarkers** using:
   - 3D Segmented CT scans (maybe PET)
   - Biopsy confirmed IHC markers (maybe genomic too)
   - Age
   - Gender

2. **Building a "virtual biopsy"** to support radiologists during diagnosis

3. **Multi-label classification problem** - predicting multiple biomarkers simultaneously

---

## Current Project Status

### ✅ **What You Have:**

1. **Basic CT Scan Analysis**
   - ✅ Upload and process CT scan images (2D: JPEG, PNG, DICOM)
   - ✅ AI model for lung cancer classification (ResNet-50 based)
   - ✅ Nodule detection with malignancy scores
   - ✅ Classification into: Normal, Adenocarcinoma, Large Cell Carcinoma, Squamous Cell Carcinoma

2. **Patient Data Management**
   - ✅ Patient records (name, date of birth, medical record number)
   - ✅ Age calculation from date of birth
   - ✅ Case management system

3. **Clinical Workflow**
   - ✅ Interactive scan viewer with nodule overlays
   - ✅ Report generation
   - ✅ Case tracking and notes

### ❌ **What's Missing (Critical Gaps):**

1. **3D Segmentation**
   - ❌ Currently only processes 2D images
   - ❌ No 3D CT scan segmentation capability
   - ❌ No support for multi-slice DICOM volumes

2. **Biomarker Prediction**
   - ❌ No IHC (Immunohistochemistry) marker prediction
   - ❌ No genomic biomarker prediction
   - ❌ Model only predicts cancer type, not specific biomarkers

3. **Patient Demographics Integration**
   - ❌ **Gender field is missing** from patient schema
   - ❌ Age and gender are **not used as model inputs**
   - ❌ Model only takes images, not patient metadata

4. **Multi-Label Classification**
   - ❌ Current model is **single-label** (one class per image)
   - ❌ No multi-label output for multiple biomarkers
   - ❌ No simultaneous prediction of multiple IHC markers

5. **Virtual Biopsy Functionality**
   - ❌ No biomarker prediction that mimics biopsy results
   - ❌ No IHC marker output (e.g., PD-L1, EGFR, ALK, etc.)
   - ❌ No genomic mutation prediction

---

## Gap Analysis

| Requirement | Status | Notes |
|------------|--------|-------|
| 3D Segmented CT scans | ❌ Missing | Only 2D image processing |
| PET scan support | ❌ Missing | Not implemented |
| IHC marker prediction | ❌ Missing | No biomarker outputs |
| Genomic biomarker prediction | ❌ Missing | Not implemented |
| Age as model input | ❌ Missing | Age collected but not used in model |
| Gender as model input | ❌ Missing | Gender field doesn't exist |
| Multi-label classification | ❌ Missing | Single-label only |
| Virtual biopsy | ❌ Missing | No biomarker predictions |

---

## Recommendations to Meet Requirements

### 1. **Add Gender Field**
```python
# In backend/app/core/schemas.py
class PatientCreate(BaseModel):
    # ... existing fields ...
    gender: Literal["Male", "Female", "Other"] = Field(..., description="Patient gender")
```

### 2. **Implement 3D CT Scan Processing**
- Add DICOM volume loading (multi-slice support)
- Implement 3D segmentation (e.g., using nnU-Net, 3D U-Net)
- Process entire CT volumes, not just single slices

### 3. **Add Biomarker Prediction**
- Extend model to output multiple biomarkers:
  - PD-L1 expression (positive/negative)
  - EGFR mutation status
  - ALK rearrangement
  - KRAS mutation
  - Other actionable mutations
- Convert from single-label to multi-label classification

### 4. **Integrate Patient Demographics**
- Modify model architecture to accept:
  - Image features (from CNN)
  - Age (normalized)
  - Gender (encoded)
- Use a multi-modal architecture that combines imaging and clinical data

### 5. **Implement Multi-Label Classification**
- Change model output from 4 classes to multiple binary outputs
- Use sigmoid activation + binary cross-entropy loss
- Output format: `{PD-L1: 0.85, EGFR: 0.12, ALK: 0.03, ...}`

### 6. **Build Virtual Biopsy Interface**
- Display predicted biomarkers in a report format
- Show confidence scores for each biomarker
- Compare with actual biopsy results (if available)
- Generate biomarker report similar to pathology report

---

## Example Target Architecture

```
Input:
├── 3D CT Scan Volume (segmented)
├── Age: 65
└── Gender: Male

Model:
├── 3D CNN Encoder (for CT volume)
├── Clinical Data Encoder (for age/gender)
└── Multi-Modal Fusion Layer

Output (Multi-Label):
├── PD-L1 Expression: 0.87 (positive)
├── EGFR Mutation: 0.15 (negative)
├── ALK Rearrangement: 0.02 (negative)
├── KRAS Mutation: 0.08 (negative)
└── ... (other biomarkers)
```

---

## Conclusion

**Current Status: ❌ Does NOT fully satisfy requirements**

Your project is a **good foundation** for lung cancer detection, but it's missing the core requirements:

1. **3D segmentation** and processing
2. **Biomarker prediction** (IHC markers, genomic mutations)
3. **Multi-label classification** architecture
4. **Patient demographics integration** (especially gender)
5. **Virtual biopsy** functionality

**Next Steps:**
1. Add gender field to patient schema
2. Implement 3D DICOM volume processing
3. Redesign model for multi-label biomarker prediction
4. Integrate age and gender as model inputs
5. Build virtual biopsy report interface

The project currently focuses on **nodule detection and cancer type classification**, but the requirements call for **biomarker prediction** (a "virtual biopsy") which is a more advanced application.


