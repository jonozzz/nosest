{% extends "base.tpl" %}
{% block bvt_active %}active{% endblock %}

{% block title %}BIG-IQ User Build Request - Internal Test Page{% endblock %}

{% block description %}
     <h2>Internal Test Page (BIG-IQ User Build Request)</h2>
     <p>This is intended for Developers to validate user builds against existing Nose test suites (or subsets of such suites). Note that if the <code>ISO</code> parameter is not specified, the latest build from <span class="label label-inverse">bigiq-mgmt-cm</span> branch will be assumed. Click on the dotted links to edit values. Check out the console tab for any log messages.</p>
{% endblock %}

{% block options %}
                <table id="options" class="table table-bordered table-striped" style="clear: both">
                    <tbody> 
                        <tr>         
                            <td width="16%" rowspan="2">BIG-IQ Custom ISO</td>
                            <td width="4%">Base:</td>
                            <td width="35%"><a href="#" id="iso" data-bind="editable: inputs.iso" data-type="text" data-inputclass="input-xxlarge" data-placeholder="Required" data-emptytext="Click to enter path to your dev iso" data-original-title="Enter the path to the ISO file"></a></td>
                            <td width="45%"><span class="muted">e.g.: /build/bigiq/project/bigiq-mgmt-cm/daily/build7932.0/BIG-IQ-bigiq-mgmt-cm-4.6.0.0.0.7932.iso (default: current build)</span></td>
                        </tr>
                        <tr>         
                            <td>Hotfix:</td>
                            <td><a href="#" id="hfiso" data-bind="editable: inputs.hfiso" data-type="text" data-inputclass="input-xxlarge" data-placeholder="Required" data-emptytext="Optional" data-original-title="Enter the path to the ISO file"></a></td>
                            <td><span class="muted">e.g.: /build/bigiq/v4.5.0-hf2/daily/build7131.0/Hotfix-BIG-IQ-4.5.0-2.0.7131-HF2.iso</span></td>
                        </tr>
                        <tr>         
                            <td colspan="4" height="20" class="muted">~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~</td>
                        </tr>
                        <tr>         
                            <td colspan="2">BIG-IP Version in Harness</td>
                            <td><a href="#" id="bigip_v" data-bind="editable: inputs.bigip_v" data-type="select" data-placeholder="Required" data-original-title="Select the BIGIP version to use:"></a></td>
                            <td><span class="muted">For BP DUTs (includes latest released hf - or latest such build)</span></td>
                        </tr>
                        <tr>         
                            <td colspan="4" class="muted">BIG-IP Custom ISO is Optional (instead of "BIG-IP Version" above). Using Custom ISO overrides defaults.</td>
                        </tr>
                        <tr>
                             <td rowspan="2">BIG-IP Custom ISO</td>
                             <td width="5%">Base:</td>
                             <td><a href="#" id="custom_bigip_iso" data-bind="editable: inputs.custom_bigip_iso" data-type="text" data-emptytext="Optional - BIG-IP Base Iso" data-original-title="Enter the path to the ISO file"></a></td>
                             <td><span class="muted">e.g.: /build/bigip/v11.6.0/dist/release/BIGIP-11.6.0.0.0.401.iso</span></td>
                        </tr>
                        <tr>
                            <td>Hotfix:</td>
                            <td><a href="#" id="custom_bigip_hf_iso" data-bind="editable: inputs.custom_bigip_hf_iso" data-type="text" data-emptytext="Optional - BIG-IP HF Iso" data-original-title="Enter the path to the hotfix ISO file"></a></td>
                            <td><span class="muted">e.g.: /build/bigip/v11.6.0-hf6/dist/release/Hotfix-BIGIP-11.6.0.6.0.442-HF6.iso</span></td>
                        </tr>
                        <tr>         
                            <td colspan="4" height="40%" class="muted">~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~</td>
                        </tr>
                        <tr>         
                            <td colspan="2">Test Run Type</td>
                            <td><a href="#" id="testruntype" data-bind="editable: inputs.testruntype" data-type="select" data-placeholder="Required" data-original-title="Select the test run type to execute:"></a></td>
                            <td><span class="muted">Which type of test run to execute.</span></td>
                        </tr>
                        <tr>
                            <td colspan="2">Module</td>
                            <td><a href="#" id="module" data-bind="editable: inputs.module" data-type="checklist" data-original-title="Select modules"></a></td>
                            <td><span class="muted">Modules (for ASM - choose only ASM - as a separate run).</span></td>
                        </tr>
                        <tr>
                            <td colspan="2">UI vs API</td>
                            <td>
                                <a href="#" id="ui" class="hide" data-bind="editable: inputs.ui" data-type="select"></a>
	                            <div>
	                                <button type="button" class="btn btn-mini" data-bind="toggle: inputs.ui() == 'api', click: function(){ inputs.ui('api') }">API</button>
	                                <button type="button" class="btn btn-mini" data-bind="toggle: inputs.ui() == 'ui', click: function(){ inputs.ui('ui') }">UI</button>
	                                <button type="button" class="btn btn-mini" data-bind="toggle: !inputs.ui(), click: function(){ inputs.ui(false) }">API + UI</button>
	                            </div>
							</td>
                            <td><span class="muted">Include UI tests?</span></td>
                        </tr>
                        <tr>
                            <td colspan="2">High Availability</td>
                            <td><a href="#" id="ha" data-bind="editable: inputs.ha" data-type="checklist" data-original-title="Selection"></a></td>
                            <td><span class="muted">Include any HA tests in addition to standalone?</span></td>
                        </tr> 
                        <tr>        
                            <td colspan="4" height="50%" class="muted">~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~</td>
                        </tr>
                        <tr>
                            <td colspan="2">Send Email Report To:</td>
                            <td><a href="#" id="email" data-bind="editable: inputs.email" data-type="text" data-emptytext="Enter Your F5 Email Address Here..." data-original-title="Enter an email"></a></td>
                            <td><span class="muted">Who receives test report. Separate by ;</span></td>
                        </tr>
                    </tbody>
                </table>
{% endblock %}

{% block head %}
    <link href="/media/select2/select2.css" rel="stylesheet">
    <script src="/media/select2/select2.js"></script>

{% endblock %}

{% block js %}
    <script src="/media/app.internaltest.js"></script>
{% endblock %}
