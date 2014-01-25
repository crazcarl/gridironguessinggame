$(document).ready(function() {
	
	$("#submit").click(function() {
		//do validation here:
		var mnfScore = $("#tiebreak").val();
		if (isNaN(mnfScore)) {
			alert("You didn't enter a valid MNF score. It's been replaced with 0. You can resubmit picks");
		}
		
		// use getelementsbyID (or by name) to get an array of all the picks. Then use that to loop
		// and check that they all have picks
	});
});