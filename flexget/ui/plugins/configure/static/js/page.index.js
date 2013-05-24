var currentUrl = ""
var interval = setInterval(function() {
	var hash = window.location.hash.substring(1);
	if (hash != currentUrl) {
		navigateTo(hash);
	}
}, 100);

$('#url-bar').keydown(function (e) {
    if (e.keyCode == 13) {
        $('#go').click();
    }
});

$('#go').click(function () {
	var itemUrl = $('#url-bar').val();
	navigateTo(itemUrl);
});

function navigateTo(itemUrl, req) {
	currentUrl = itemUrl;
	window.location = "#" + itemUrl;
	$('#url-bar').val(itemUrl);

	if (req == undefined) {
		req = Jsonary.getData(itemUrl);
	}
	$('#main').empty().addClass("loading");
	window.scrollTo(0, 0);
	req.getData(function(data, request) {
		$('#main').removeClass("loading").empty().renderJson(data);//.editableCopy()
	});
}

Jsonary.addLinkHandler(function(link, data, request) {
	navigateTo(link.href, request);
	return true;
});
