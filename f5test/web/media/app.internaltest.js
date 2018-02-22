$(function(){

    //defaults
    $.fn.editable.defaults.send = 'never'; 
    $.fn.editable.defaults.emptytext = 'Click to edit';
    //var default_modules = ['access', 'adc', 'afm', 'asm', 'avr', 'cloud', 'device', 'security', 'system', 'platform'];
//    var allowed_modules = [
//                           {value: 'asm', text: "asm"},
//                           {value: 'access', text: "access"}
//                           ]; 
    
    var allowed_modules = ['asm', 'access', 'adc','afm', 'avr', 'device', 'system', 'platform'];
    var default_modules = ['access', 'adc', 'afm', 'avr', 'device', 'system', 'platform'];

    //editables
    $('#bigip_v').editable({
        //value: '12.0.0',
        source: [
              {value: '11.5.3', text: "11.5.3"},
              {value: '11.5.4', text: "11.5.4"},
              {value: '11.6.0', text: "11.6.0"},
              {value: '11.6.1', text: "11.6.1"},
              {value: '12.0.0', text: "12.0.0"},
              {value: '12.0.0 hf-x', text: "12.0.0 hf-x"},
              {value: '12.0.0 hf-tmos', text: "12.0.0 hf-tmos"},
              {value: '12.1.0', text: "12.1.0"},
              {value: '12.1.1', text: "12.1.1"},
              {value: 'tmos-tier2', text: "tmos-tier2"}
        ]
    });
    $('#module').editable({
        //inputclass: 'input-large',
        showbuttons: true,
        emptytext: "Select Module...",
        value: default_modules,
        //select2: {
        source: allowed_modules
    });
    $('#ha').editable({
        showbuttons: true,
        emptytext: 'Anything',
        source: [
              {value: 'standalone', text: "Standalone"},
              //{value: 'aa', text: "Active-Active"},
              {value: 'as', text: "Active-Standby"}
        ]
    });

    $('#user .editable').on('hidden', function(e, reason){
         if(reason === 'save' || reason === 'nochange') {
             var $next = $(this).closest('tr').next().find('.editable');
             if($('#autoopen').is(':checked')) {
                 setTimeout(function() {
                     $next.editable('show');
                 }, 300); 
             } else {
                 $next.focus();
             } 
         }
    });
    $('#testruntype').editable({
        //value: 'BQ BVT (rank 1-10)',
        source: [
              {value: 'biq-standard-bvt', text: "BQ BVT (rank 1-10)"},
              {value: 'bip-signoff-bvt', text: "BP Signoff (rank 5-10)"},
              {value: 'biq-functional', text: "BQ Functional (rank 101-110)"},
              //{value: 'biq-functional-asm-legacy', text: "BQ FNC Sec Legacy (rank 505)"},
              {value: 'biq-smoke', text: "BQ Smoke (rank 2 or 6)"}
        ]
    });

    var MyTask = Task.extend({
    
        // Define the default values for the model's attributes
        defaults: {
        },

        constructor: function(attributes, options){
            this.constructor.__super__.constructor();
        },

        // Attributes
        task_uri: '/bvt/deviso',
        inputs: ko.mapping.fromJS({
          iso: ko.observable().extend({ remote: { type: 'file' }, required: false }),
          hfiso: ko.observable().extend({ remote: { type: 'file' }, required: false }),
          bigip_v: ko.observable('12.0.0'),
          email: ko.observable(),
          custom_bigip_iso: ko.observable(),
          custom_bigip_hf_iso: ko.observable(),
          ha: ko.observableArray([]),
          module: ko.observableArray(default_modules),
          ui: ko.observable(false),
          testruntype: ko.observable('biq-standard-bvt')
        }),

        // Methods
        /*refresh: function() {
            console.log('refreshed');
        },*/

    });

    var task = new MyTask();
    task.setup_routes();
    ko.applyBindings(task);

});
