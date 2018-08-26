<script type="text/javascript">
	function insert_chart(metric, seconddiv) {
		var spec = "./" + metric + ".json"; 
		if(!seconddiv) { 
		    var idname = "#" + metric;
	    } else {
            var idname = "#" + seconddiv;
        }
		vegaEmbed(idname, spec, {actions: false}).then(function(result) {}).catch(console.error);
	}
	insert_chart('DM_Eye_Exam');
	insert_chart('DM_Eye_Exam', 'DM_Eye_Exam_2');
	insert_chart('DM_Foot_Exam');
	insert_chart('DM_Foot_Exam', 'DM_Foot_Exam_2');
	insert_chart('DM_Nephropathy');
	insert_chart('DM_Nephropathy', 'DM_Nephropathy_2');
	insert_chart('DM_Pneumovax');
	insert_chart('DM_Pneumovax', 'DM_Pneumovax_2');
	insert_chart('DM_with_ACE_or_ARB');
	insert_chart('DM_with_Statin');
	insert_chart('Colorectal_Screen');
	insert_chart('Colorectal_Screen', 'Colorectal_Screen_2');
	insert_chart('Pap_Smears');
	insert_chart('Pap_Smears', 'Pap_Smears_2');
	insert_chart('Mammogram');
	insert_chart('Mammogram', 'Mammogram_2');
	insert_chart('Chlamydia');
	insert_chart('AAA');
	insert_chart('Over_age_65_Pneumovax');
	insert_chart('Smoker_Pneumovax');
	insert_chart('TD_and_TDAP');
	insert_chart('TD_and_TDAP', 'TD_and_TDAP_2');
</script>