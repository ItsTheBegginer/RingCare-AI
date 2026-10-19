import React from 'react';
import { X, CheckCircle, ArrowDown, Shield, Cpu, Eye, Radio, Server, Globe } from 'lucide-react';

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
                RingCare AI Architecture & API Contract
              </h3>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Frontend prototype with dedicated mock API service abstraction layer
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
          {/* Pipeline Diagram */}
        <div className="my-5 p-4 rounded-lg bg-slate-50 border border-slate-200">
          <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">
            Pipeline Progression
          </h4>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-2 text-center text-xs">
            <div className="p-2.5 rounded bg-white border border-slate-200 shadow-xs">
              <Radio className="w-4 h-4 text-teal-600 mx-auto mb-1" />
              <div className="font-semibold text-slate-800">1. Ring Camera</div>
              <div className="text-[10px] text-slate-500 mt-0.5">Motion / Video Stream</div>
            </div>

            <div className="hidden md:flex items-center justify-center text-slate-400">
              <ArrowDown className="w-4 h-4 -rotate-90 text-teal-600" />
            </div>

            <div className="p-2.5 rounded bg-amber-50/70 border border-amber-200 shadow-xs">
              <Eye className="w-4 h-4 text-amber-600 mx-auto mb-1" />
              <div className="font-semibold text-amber-900">2. OpenCV</div>
              <div className="text-[10px] text-amber-700 mt-0.5">Motion & Person Tracking</div>
            </div>

            <div className="hidden md:flex items-center justify-center text-slate-400">
              <ArrowDown className="w-4 h-4 -rotate-90 text-teal-600" />
            </div>

            <div className="p-2.5 rounded bg-purple-50/70 border border-purple-200 shadow-xs">
              <Cpu className="w-4 h-4 text-purple-600 mx-auto mb-1" />
              <div className="font-semibold text-purple-900">3. AI Agent</div>
              <div className="text-[10px] text-purple-700 mt-0.5">Triage & Assessment</div>
            </div>
          </div>

          <div className="flex justify-center my-2">
            <ArrowDown className="w-4 h-4 text-slate-400" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded bg-white border border-slate-200 shadow-xs flex items-start gap-2.5">
              <Server className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-slate-800 block">4. REST API (FastAPI / Express)</span>
                <span className="text-[11px] text-slate-500">
                  Exposes endpoints: <code>/api/events</code>, <code>/api/cameras</code>, <code>/api/dashboard/summary</code>
                </span>
              </div>
            </div>

            <div className="p-3 rounded bg-teal-50 border border-teal-200 shadow-xs flex items-start gap-2.5">
              <Globe className="w-4 h-4 text-teal-700 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-teal-900 block">5. Frontend Client (This Dashboard)</span>
                <span className="text-[11px] text-slate-600">
                  Consumes <code>services/api.ts</code> with zero UI rewrite needed when backend connects.
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* API Contract Table */}
        <div className="space-y-3">
          <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
            Future REST API Endpoints Contract
          </h4>

          <div className="overflow-x-auto text-xs font-mono">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-slate-600">
                  <th className="py-1.5 px-2">Method</th>
                  <th className="py-1.5 px-2">Endpoint</th>
                  <th className="py-1.5 px-2 font-sans">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-800">
                <tr>
                  <td className="py-1.5 px-2 text-emerald-700 font-semibold">GET</td>
                  <td className="py-1.5 px-2">/api/events</td>
                  <td className="py-1.5 px-2 font-sans text-slate-600">Fetch filtered activity & triage events</td>
                </tr>
                <tr>
                  <td className="py-1.5 px-2 text-emerald-700 font-semibold">GET</td>
                  <td className="py-1.5 px-2">/api/events/:id</td>
                  <td className="py-1.5 px-2 font-sans text-slate-600">Retrieve single event CV and AI assessment</td>
                </tr>
                <tr>
                  <td className="py-1.5 px-2 text-blue-700 font-semibold">POST</td>
                  <td className="py-1.5 px-2">/api/events/:id/acknowledge</td>
                  <td className="py-1.5 px-2 font-sans text-slate-600">Mark event reviewed & approved by caregiver</td>
                </tr>
                <tr>
                  <td className="py-1.5 px-2 text-amber-700 font-semibold">POST</td>
                  <td className="py-1.5 px-2">/api/events/:id/dismiss</td>
                  <td className="py-1.5 px-2 font-sans text-slate-600">Dismiss non-critical motion event</td>
                </tr>
                <tr>
                  <td className="py-1.5 px-2 text-emerald-700 font-semibold">GET</td>
                  <td className="py-1.5 px-2">/api/cameras</td>
                  <td className="py-1.5 px-2 font-sans text-slate-600">Retrieve connected Ring camera states & health</td>
                </tr>
                <tr>
                  <td className="py-1.5 px-2 text-emerald-700 font-semibold">GET</td>
                  <td className="py-1.5 px-2">/api/dashboard/summary</td>
                  <td className="py-1.5 px-2 font-sans text-slate-600">Aggregated daily metrics for care dashboard</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer note */}
        <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs text-emerald-700 font-medium">
            <CheckCircle className="w-4 h-4" />
            <span>Clean Service Seam Ready for Python / Node Backend</span>
          </div>
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
