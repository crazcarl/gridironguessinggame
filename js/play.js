$(document).ready(function() {
		
	$("#submit").click(function() {
		//do validation here:
		var mnfScore = $("#tiebreak").val();

		if (0 === mnfScore.length || isNaN(mnfScore)) {
			alert("You didn't enter a valid MNF score. It's been replaced with 0. You can resubmit picks");
		}
		
		var rtnodes = document.getElementsByClassName("righttd");
		var lfnodes = document.getElementsByClassName("lefttd");
		var user = document.getElementById("login");
		for(var i=0; i < rtnodes.length; i++) {
			if (!rtnodes[i].checked && !lfnodes[i].checked && user.innerHTML != "Welcome winner") {
				j=i+1;
				alert("Hey you missed game " + j + "!" + "\n we picked the home team for you");
				lfnodes[i].checked = true;
			}
		};
	});
})