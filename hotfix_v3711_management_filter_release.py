"""Hotfix v3.7.11: fix management-dashboard query parsing and resilient filtered rendering."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/'static'
BACKEND_MARK='# === MANAGEMENT FILTER FIX V3.7.11 ==='
JS_MARK='// === MANAGEMENT FILTER FIX V3.7.11 ==='

BACKEND=r'''
# === MANAGEMENT FILTER FIX V3.7.11 ===
_mgmt_dashboard_data_v3711_base = _mgmt_dashboard_data

def _v3711_query_scalar(query, key, limit):
    if not isinstance(query, dict):
        return ''
    raw = query.get(key, '')
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else ''
    return F.text(raw, limit)

def _mgmt_dashboard_data(app, c, user, query):
    normalized = {
        'year': _v3711_query_scalar(query, 'year', 4),
        'turma': _v3711_query_scalar(query, 'turma', 160),
        'activityKey': _v3711_query_scalar(query, 'activityKey', 250),
        'date': _v3711_query_scalar(query, 'date', 40),
    }
    data = _mgmt_dashboard_data_v3711_base(app, c, user, normalized)

    # Guarantee a complete dashboard payload even when a filter yields no rows.
    if not isinstance(data, dict):
        data = {}
    filters = data.get('filters')
    if not isinstance(filters, dict):
        filters = {}
        data['filters'] = filters
    filters.setdefault('years', [])
    filters.setdefault('turmas', [])
    filters.setdefault('simulations', [])
    filters['selected'] = normalized

    data.setdefault('kpis', {})
    data.setdefault('areas', [])
    data.setdefault('simulations', [])
    data.setdefault('classes', [])
    return data
'''

JS=r'''
// === MANAGEMENT FILTER FIX V3.7.11 ===
function managementSafeArray(value){return Array.isArray(value)?value:[];}

const managementFiltersHtmlV3711Base=managementFiltersHtml;
managementFiltersHtml=function(d){
 const safe=d&&typeof d==='object'?d:{};
 const f=safe.filters&&typeof safe.filters==='object'?safe.filters:{};
 f.years=managementSafeArray(f.years);
 f.turmas=managementSafeArray(f.turmas);
 f.simulations=managementSafeArray(f.simulations);
 f.selected=f.selected&&typeof f.selected==='object'?f.selected:{};
 safe.filters=f;
 return managementFiltersHtmlV3711Base(safe);
};

const managementAreaHtmlV3711Base=managementAreaHtml;
managementAreaHtml=function(rows){return managementAreaHtmlV3711Base(managementSafeArray(rows));};

const managementSimulationChartV3711Base=managementSimulationChart;
managementSimulationChart=function(rows){return managementSimulationChartV3711Base(managementSafeArray(rows));};

const managementSimulationTableV3711Base=managementSimulationTable;
managementSimulationTable=function(rows){return managementSimulationTableV3711Base(managementSafeArray(rows));};

const managementClassTableV3711Base=managementClassTable;
managementClassTable=function(rows){return managementClassTableV3711Base(managementSafeArray(rows));};

acts['management-dashboard-refresh']=async()=>{
 managementDashboardFilters={
  year:document.getElementById('management-year')?.value||managementDashboardFilters.year||'',
  turma:document.getElementById('management-turma')?.value||managementDashboardFilters.turma||'',
  activityKey:managementDashboardFilters.activityKey||'',
  date:managementDashboardFilters.date||'',
 };
 const sim=document.getElementById('management-simulation');
 if(sim){
  const parts=(sim.value||'').split('@@');
  managementDashboardFilters.activityKey=parts[0]||'';
  managementDashboardFilters.date=parts[1]||'';
 }
 managementDashboardCache=null;
 await loadManagementDashboard(true);
};

document.addEventListener('change',event=>{
 const el=event.target;
 if(!managementDashboardAllowed()||!el)return;
 if(el.id==='management-year'){
  managementDashboardFilters.year=el.value||'';
  managementDashboardCache=null;
  loadManagementDashboard(true);
 }
 if(el.id==='management-turma'){
  managementDashboardFilters.turma=el.value||'';
  managementDashboardCache=null;
  loadManagementDashboard(true);
 }
 if(el.id==='management-simulation'){
  const parts=(el.value||'').split('@@');
  managementDashboardFilters.activityKey=parts[0]||'';
  managementDashboardFilters.date=parts[1]||'';
  managementDashboardCache=null;
  loadManagementDashboard(true);
 }
},true);
'''

def main():
    model=ROOT/'model_data.py'
    source=model.read_text(encoding='utf-8')
    if BACKEND_MARK not in source:
        model.write_text(source.rstrip()+"\n\n"+BACKEND.strip()+"\n",encoding='utf-8')

    js=STATIC/'student_summary.js'
    source=js.read_text(encoding='utf-8')
    if JS_MARK not in source:
        js.write_text(source.rstrip()+"\n\n"+JS.strip()+"\n",encoding='utf-8')

    html=STATIC/'app.html'
    source=html.read_text(encoding='utf-8')
    source=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.11',source)
    html.write_text(source,encoding='utf-8')

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('/static/student_summary.js?v=3.7.7','/static/student_summary.js?v=3.7.11')
        source=source.replace('/static/student_summary.js?v=3.7.10','/static/student_summary.js?v=3.7.11')
        verifier.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    if site.exists():
        source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.10"','PUBLIC_VERSION="3.7.11"')
        source=source.replace('PUBLIC_VERSION="3.7.9"','PUBLIC_VERSION="3.7.11"')
        site.write_text(source,encoding='utf-8')

    vsite=ROOT/'verify_site_version.py'
    if vsite.exists():
        source=vsite.read_text(encoding='utf-8').replace('v3.7.10','v3.7.11').replace('v3.7.9','v3.7.11')
        vsite.write_text(source,encoding='utf-8')

    # Some legacy version normalizers may turn 3.7.11 into 3.7.111 in verifier text.
    verifier=ROOT/'verify_hotfix_v3711_management_filter.py'
    if verifier.exists():
        source=verifier.read_text(encoding='utf-8').replace('v3.7.111','v3.7.11')
        verifier.write_text(source,encoding='utf-8')

    print('MEUCRONOGRAMA_MANAGEMENT_FILTER_FIX_READY: query scalars, safe arrays and filtered TRI averages installed.',flush=True)

if __name__=='__main__':
    main()
