redef tcp_content_deliver_all_orig = T;
redef tcp_content_deliver_all_resp = T;

event tcp_contents(c: connection, is_orig: bool, seq: count, contents: string)
	{
	if ( |contents| == 0 )
		return;

	local payload = sub_bytes(contents, 0, 64);
	local src_h = is_orig ? c$id$orig_h : c$id$resp_h;
	local src_p = is_orig ? c$id$orig_p : c$id$resp_p;
	local dst_h = is_orig ? c$id$resp_h : c$id$orig_h;
	local dst_p = is_orig ? c$id$resp_p : c$id$orig_p;

	print fmt("MLNM|%s|%d|%s|%d|%s",
		src_h, src_p, dst_h, dst_p, bytestring_to_hexstr(payload));
	}
