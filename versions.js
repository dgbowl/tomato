arr = window.location.href.split('/');
page = arr[arr.length - 1];
document.write('\
<dl>\
    <dt>Versions</dt> \
    <dd><a href="../master/' + page + '">master</a></dd>\
</dl>\
');