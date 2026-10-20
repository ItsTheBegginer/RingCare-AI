import React from 'react';
import { X, Shield, Radio, Server, Eye, Cpu, Database, ArrowRight, AlertTriangle } from 'lucide-react';

interface ArchitectureModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ArchitectureModal: React.FC<ArchitectureModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in">
      <div className="relative w-full max-w-2xl bg-white border border-slate-200 rounded-xl shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-slate-800 bg-[#0c1322] text-white">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-teal-500/20 text-teal-400 border border-teal-500/30">
                <Shield className="w-4 h-4" />
              </span>
              <h3 className="text-base font-semibold text-white">
                How it works &amp; Limitations
              </h3>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              RingCare AI · Real production pipeline
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6">
          {/* How it works */}
          <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">
            How it works
          </h4>

          {/* Pipeline — 5 columns on md+, stacked on mobile */}
          <div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-0">
            {/* Step 1 */}
            <div className="flex-1 p-2.5 rounded bg-white border border-slate-200 shadow-xs text-center text-xs">
              <Radio className="w-4 h-4 text-teal-600 mx-auto mb-1" />
              <div className="font-semibold text-slate-800">Ring Camera</div>
              <div className="text-[10px] text-slate-500 mt-0.5">Motion event detected</div>
            </div>

            <ArrowRight className="hidden md:block w-4 h-4 text-teal-600 shrink-0 mx-1" />

            {/* Step 2 */}
            <div className="flex-1 p-2.5 rounded bg-white border border-slate-200 shadow-xs text-center text-xs">
              <Server className="w-4 h-4 text-indigo-600 mx-auto mb-1" />
              <div className="font-semibold text-slate-800">FastAPI Backend</div>
              <div className="text-[10px] text-slate-500 mt-0.5">Download clip, run analysis</div>
            </div>

            <ArrowRight className="hidden md:block w-4 h-4 text-teal-600 shrink-0 mx-1" />

            {/* Step 3 */}
            <div className="flex-1 p-2.5 rounded bg-amber-50/70 border border-amber-200 shadow-xs text-center text-xs">
              <Eye className="w-4 h-4 text-amber-600 mx-auto mb-1" />
              <div className="font-semibold text-amber-900">Rekognition + OpenCV</div>
              <div className="text-[10px] text-amber-700 mt-0.5">Person detection &amp; labels</div>
            </div>

            <ArrowRight className="hidden md:block w-4 h-4 text-teal-600 shrink-0 mx-1" />

            {/* Step 4 */}
            <div className="flex-1 p-2.5 rounded bg-purple-50/70 border border-purple-200 shadow-xs text-center text-xs">
              <Cpu className="w-4 h-4 text-purple-600 mx-auto mb-1" />
              <div className="font-semibold text-purple-900">Rules Engine (assess.py)</div>
              <div className="text-[10px] text-purple-700 mt-0.5">Evidence-based assessment</div>
            </div>

            <ArrowRight className="hidden md:block w-4 h-4 text-teal-600 shrink-0 mx-1" />

            {/* Step 5 */}
            <div className="flex-1 p-2.5 rounded bg-white border border-slate-200 shadow-xs text-center text-xs">
              <Database className="w-4 h-4 text-slate-600 mx-auto mb-1" />
              <div className="font-semibold text-slate-800">DynamoDB + SNS + Dashboard</div>
              <div className="text-[10px] text-slate-500 mt-0.5">Store, alert, display</div>
            </div>
          </div>

          {/* Known Limitations */}
          <div className="mt-5 rounded-lg bg-amber-50 border border-amber-200 p-4">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              <span className="text-xs font-semibold text-amber-900">Known Limitations</span>
            </div>
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1.5 text-[11px] text-amber-800 list-disc list-inside">
              <li>Playground access token expires ~30 minutes</li>
              <li>Ring API returns watermarked video</li>
              <li>Single-frame detection — no temporal pose tracking</li>
              <li>Clip window is 10 seconds</li>
              <li>No guaranteed fall or weapon detection</li>
              <li>Does not contact emergency services</li>
              <li>No away mode or scheduled monitoring</li>
              <li>All analysis is advisory only — verify in person</li>
            </ul>
          </div>

          {/* Footer */}
          <div className="mt-5 pt-4 border-t border-slate-100 flex justify-end">
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-xs font-medium text-white bg-slate-800 hover:bg-slate-900 rounded-lg transition-colors shadow-xs"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
