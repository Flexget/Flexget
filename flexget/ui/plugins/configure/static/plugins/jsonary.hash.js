(function (global) {
	var hashJsonaryData = Jsonary.create(null);

	var addHistoryPoint = false;
	hashJsonaryData.addHistoryPoint = function () {
		addHistoryPoint = true;
	};

	var ignoreUpdates = false;
	var lastHash = null;
	function updateHash() {
		var hashString = window.location.hash;
		if (hashString.length > 0 && hashString.charAt(0) == "#") {
			hashString = hashString.substring(1);
		}
		if (hashString == lastHash) {
			return;
		}
		lastHash = hashString;
		
		var hashData = hashString;
		try {
			hashData = Jsonary.decodeData(hashString, "application/x-www-form-urlencoded");
		} catch (e) {
			console.log(e);
		}
		ignoreUpdate = true;
		hashJsonaryData.setValue(hashData);
		ignoreUpdate = false;
	}
	
	setInterval(updateHash, 100);
	updateHash();
	
	var changeListeners = [];
	hashJsonaryData.document.registerChangeListener(function (patch) {
		for (var i = 0; i < changeListeners.length; i++) {
			changeListeners[i].call(hashJsonaryData, hashJsonaryData);
		}

		if (ignoreUpdate) {
			ignoreUpdate = false;
			return;
		}
		lastHash = Jsonary.encodeData(hashJsonaryData.value(), "application/x-www-form-urlencoded").replace("%2F", "/");
		if (addHistoryPoint) {
			window.location.href = "#" + lastHash;
		} else {
			window.location.replace("#" + lastHash);
		}
	});
	hashJsonaryData.onChange = function (callback) {
		changeListeners.push(callback);
		callback.call(hashJsonaryData, hashJsonaryData);
	};

	Jsonary.extend({
		hash: hashJsonaryData
	});	
	
})(this);
