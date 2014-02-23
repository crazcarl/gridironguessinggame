$(document).ready(function() {
	
	$("#submit").click(function() {
		//do validation here:
		var mnfScore = $("#tiebreak").val();
		if (isNaN(mnfScore)) {
			alert("You didn't enter a valid MNF score. It's been replaced with 0. You can resubmit picks");
		}
		
		var rtnodes = document.getElementsByClassName("righttd");
		var lfnodes = document.getElementsByClassName("lefttd");	});
		for(var i=0; i < rtnodes.length; i++) {
			if (!rtnodes[i].checked && !lfnodes[i].checked) {
				alert("hey " + i + " is blank, son!")
			}
}