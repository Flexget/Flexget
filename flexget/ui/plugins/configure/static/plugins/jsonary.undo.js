(function () {
	var modKeyDown = false;
	var shiftKeyDown = false;
	var otherKeys = {};

	// Register key down/up listeners to catch undo/redo key combos
	document.onkeydown = function (e) {
		var keyCode = (window.event != null) ? window.event.keyCode : e.keyCode;
		if (keyCode == 17) {
			modKeyDown = true;
		} else if (keyCode == 16) {
			shiftKeyDown = true;
		} else {
			otherKeys[keyCode] = true;
		}
		var otherKeyCount = 0;
		for (var otherKeyCode in otherKeys) {
			if (otherKeyCode != 90 && otherKeyCode != 89) {
				otherKeyCount++;
			}
		}
		if (otherKeyCount == 0) {
			if (keyCode == 90) {	// Z
				if (modKeyDown) {
					if (shiftKeyDown) {
						Jsonary.redo();
					} else {
						Jsonary.undo();
					}
				}
			} else if (keyCode == 89) {	// Y
				if (modKeyDown && !shiftKeyDown) {
					Jsonary.redo();
				}
			}
		}
	};
	document.onkeyup = function (e) {
		var keyCode = (window.event != null) ? window.event.keyCode : e.keyCode;
		if (keyCode == 17) {
			modKeyDown = false;
		} else if (keyCode == 16) {
			shiftKeyDown = false;
		} else {
			delete otherKeys[keyCode];
		}
	};
	
	var undoList = [];
	var redoList = [];
	var ignoreChanges = 0;
	
	Jsonary.registerChangeListener(function (patch, document) {
		if (ignoreChanges > 0) {
			ignoreChanges--;
			return;
		}
		undoList.push({patch: patch, document: document});
		while (undoList.length > Jsonary.undo.historyLength) {
			undoList.shift();
		}
		if (redoList.length > 0) {
			redoList = [];
		}
	});
	
	Jsonary.extend({
		undo: function () {
			var lastChange = undoList.pop();
			if (lastChange != undefined) {
				ignoreChanges++;
				redoList.push(lastChange);
				lastChange.document.patch(lastChange.patch.inverse());
			}
		},
		redo: function () {
			var nextChange = redoList.pop();
			if (nextChange != undefined) {
				ignoreChanges++;
				undoList.push(nextChange);
				nextChange.document.patch(nextChange.patch);
			}
		}
	});
	Jsonary.undo.historyLength = 10;
})();
