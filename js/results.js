$(document).ready(function() {
	$( ".week_selector" ).change(function() {
		alert( "Handler for .change() called." );
	});
});


var selector = document.getElementByClassName("week_selector");
var week = selector.options[selector.selectedIndex].value;
var data={"week":week};
$.ajax({
	 type: "GET",
	 url: "/play/results",
	 data: data,
	 dataType: 'json',
	 success: function(data) {
		evaluateResult(data,bar,location)
		$('#submit').attr('disabled',false)
	 }
});