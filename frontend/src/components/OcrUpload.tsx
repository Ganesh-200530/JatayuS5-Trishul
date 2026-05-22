import { useState, useRef, useCallback } from 'react';
import { Upload, FileText, X, Loader2, AlertCircle, AlertTriangle, ShieldCheck, ShieldAlert, Eye } from 'lucide-react';
import api from '../api';
import clsx from 'clsx';

interface OcrResult {
  extracted_text: string;
  filename: string;
  document_type: string;
  medical_confidence: number;
  is_medical: boolean;
  summary: string;
  warning?: string;
}

interface OcrUploadProps {
  /** Called with the extracted text after OCR succeeds */
  onExtracted: (text: string) => void;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  medical_record: 'Medical Record',
  lab_report: 'Lab Report',
  prescription: 'Prescription',
  insurance_form: 'Insurance Form',
  referral_letter: 'Referral Letter',
  radiology_report: 'Radiology Report',
  surgical_note: 'Surgical Note',
  non_medical: 'Non-Medical Document',
  unknown: 'Unknown',
};

export default function OcrUpload({ onExtracted }: OcrUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'validating' | 'validated' | 'invalid_doc' | 'uploading' | 'done' | 'warning' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [ocrResult, setOcrResult] = useState<OcrResult | null>(null);
  const [validationMsg, setValidationMsg] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (f: File) => {
    setFile(f);
    setStatus('validating');
    setErrorMsg('');
    setOcrResult(null);
    setValidationMsg('Checking if this is a medical document…');
    if (f.type.startsWith('image/')) {
      const url = URL.createObjectURL(f);
      setPreview(url);
    } else {
      setPreview(null);
    }

    // Quick validation
    try {
      const formData = new FormData();
      formData.append('file', f);
      const res = await api.post('/ocr/validate', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      });
      const d = res.data;
      if (d.is_medical) {
        setStatus('validated');
        setValidationMsg(d.message || 'Medical document detected.');
      } else {
        setStatus('invalid_doc');
        setValidationMsg(d.message || 'This does not appear to be a medical document.');
      }
    } catch {
      // If validation fails, allow through
      setStatus('validated');
      setValidationMsg('Document accepted (quick validation unavailable).');
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  const handleUpload = async () => {
    if (!file) return;
    setStatus('uploading');
    setErrorMsg('');
    setOcrResult(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post('/ocr/extract', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      const data: OcrResult = res.data;
      setOcrResult(data);

      if (!data.is_medical) {
        setStatus('warning');
        // Don't auto-fill clinical notes for non-medical docs
      } else {
        setStatus('done');
        onExtracted(data.extracted_text || '');
      }
    } catch (err: any) {
      setStatus('error');
      setErrorMsg(err.response?.data?.detail || 'Could not read document. Try again.');
    }
  };

  const forceUseText = () => {
    if (ocrResult) {
      onExtracted(ocrResult.extracted_text || '');
      setStatus('done');
    }
  };

  const clear = () => {
    setFile(null);
    setPreview(null);
    setStatus('idle');
    setErrorMsg('');
    setOcrResult(null);
    setValidationMsg('');
  };

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">
        Upload Document (OCR)
      </label>

      {/* Drop zone */}
      {!file ? (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={clsx(
            'border-2 border-dashed rounded-md p-5 text-center cursor-pointer transition-all duration-200',
            dragOver
              ? 'border-blue-400 bg-blue-50'
              : 'border-gray-300 hover:border-blue-300 hover:bg-gray-50',
          )}
        >
          <Upload className="h-6 w-6 text-gray-400 mx-auto mb-1.5" />
          <p className="text-sm text-gray-600">
            Drop an image or PDF here, or <span className="text-blue-600 font-medium">browse</span>
          </p>
          <p className="text-xs text-gray-400 mt-0.5">
            JPG, PNG, PDF — max 10 MB
          </p>
          <input
            ref={inputRef}
            type="file"
            accept="image/*,.pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
        </div>
      ) : (
        <div className="border rounded-md p-3 bg-gray-50 animate-in">
          <div className="flex items-center gap-3">
            {preview ? (
              <img src={preview} alt="preview" className="h-12 w-12 rounded-md object-cover" />
            ) : (
              <div className="h-12 w-12 rounded-md bg-blue-50 flex items-center justify-center">
                <FileText className="h-5 w-5 text-blue-600" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{file.name}</p>
              <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(0)} KB</p>
            </div>
            <button onClick={clear} className="p-0.5 hover:bg-gray-200 rounded-md">
              <X className="h-3.5 w-3.5 text-gray-500" />
            </button>
            <button
              onClick={() => {
                if (file) {
                  const url = URL.createObjectURL(file);
                  window.open(url, '_blank');
                }
              }}
              className="p-0.5 hover:bg-blue-100 rounded-md"
              title="View document"
            >
              <Eye className="h-3.5 w-3.5 text-blue-600" />
            </button>
          </div>

          {/* Action buttons / status */}
          <div className="mt-3">
            {status === 'validating' && (
              <div className="flex items-center justify-center gap-1.5 py-1.5 text-blue-600">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span className="text-sm font-medium">{validationMsg}</span>
              </div>
            )}
            {status === 'validated' && (
              <div className="space-y-2">
                <div className="flex items-center justify-center gap-1.5 py-1 text-emerald-600">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  <span className="text-xs font-medium">{validationMsg}</span>
                </div>
                <button
                  onClick={handleUpload}
                  className="w-full h-8 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-1.5"
                >
                  <Upload className="h-3.5 w-3.5" /> Extract Text
                </button>
              </div>
            )}
            {status === 'invalid_doc' && (
              <div className="space-y-2">
                <div className="flex items-center justify-center gap-1.5 py-1 text-red-600">
                  <ShieldAlert className="h-4 w-4" />
                  <span className="text-xs font-semibold">Not a Medical Document</span>
                </div>
                <p className="text-xs text-red-600 text-center">{validationMsg}</p>
                <div className="flex gap-2">
                  <button
                    onClick={clear}
                    className="flex-1 h-7 bg-red-50 border border-red-300 text-red-700 rounded-md text-xs font-medium hover:bg-red-100 transition-colors"
                  >
                    Upload Different File
                  </button>
                  <button
                    onClick={() => setStatus('validated')}
                    className="flex-1 h-7 border border-gray-300 text-gray-600 rounded-md text-xs font-medium hover:bg-gray-100 transition-colors"
                  >
                    Use Anyway
                  </button>
                </div>
              </div>
            )}
            {status === 'idle' && (
              <button
                onClick={handleUpload}
                className="w-full h-8 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-1.5"
              >
                <Upload className="h-3.5 w-3.5" /> Extract Text
              </button>
            )}
            {status === 'uploading' && (
              <div className="flex items-center justify-center gap-1.5 py-1.5 text-blue-600">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span className="text-sm font-medium">Analyzing document…</span>
              </div>
            )}
            {status === 'done' && ocrResult && (
              <div className="space-y-2">
                <div className="flex items-center justify-center gap-1.5 py-1 text-emerald-600">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  <span className="text-sm font-medium">Medical document verified</span>
                </div>
                <div className="bg-emerald-50 border border-emerald-200 rounded-md px-2.5 py-1.5">
                  <div className="flex items-center gap-2 text-xs text-emerald-700">
                    <span className="font-medium">{DOC_TYPE_LABELS[ocrResult.document_type] || ocrResult.document_type}</span>
                    <span className="text-emerald-400">•</span>
                    <span>Confidence: {Math.round(ocrResult.medical_confidence * 100)}%</span>
                  </div>
                  {ocrResult.summary && (
                    <p className="text-xs text-emerald-600 mt-0.5">{ocrResult.summary}</p>
                  )}
                </div>
                {ocrResult.extracted_text && (
                  <div className="border border-gray-200 rounded-md">
                    <div className="flex items-center justify-between bg-gray-50 px-3 py-1.5 border-b border-gray-200 rounded-t-md">
                      <span className="text-xs font-semibold text-gray-700">Extracted Text</span>
                    </div>
                    <pre className="px-3 py-2 text-xs text-gray-700 whitespace-pre-wrap max-h-60 overflow-y-auto font-sans leading-relaxed">
                      {ocrResult.extracted_text}
                    </pre>
                  </div>
                )}
              </div>
            )}
            {status === 'warning' && ocrResult && (
              <div className="space-y-2">
                <div className="flex items-center justify-center gap-1.5 py-1 text-amber-600">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="text-sm font-semibold">Non-Medical Document Detected</span>
                </div>
                <div className="bg-amber-50 border border-amber-300 rounded-md px-3 py-2">
                  <p className="text-xs text-amber-800">
                    {ocrResult.warning}
                  </p>
                  {ocrResult.summary && (
                    <p className="text-xs text-amber-600 mt-1 italic">
                      Detected: {ocrResult.summary}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={clear}
                    className="flex-1 h-7 border border-amber-300 text-amber-700 rounded-md text-xs font-medium hover:bg-amber-50 transition-colors"
                  >
                    Upload Different File
                  </button>
                  <button
                    onClick={forceUseText}
                    className="flex-1 h-7 border border-gray-300 text-gray-600 rounded-md text-xs font-medium hover:bg-gray-100 transition-colors"
                  >
                    Use Anyway
                  </button>
                </div>
              </div>
            )}
            {status === 'error' && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-center gap-1.5 py-1.5 text-red-600">
                  <AlertCircle className="h-3.5 w-3.5" />
                  <span className="text-sm">{errorMsg}</span>
                </div>
                <button
                  onClick={handleUpload}
                  className="w-full h-7 border border-red-300 text-red-600 rounded-md text-xs font-medium hover:bg-red-50 transition-colors"
                >
                  Try Again
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
