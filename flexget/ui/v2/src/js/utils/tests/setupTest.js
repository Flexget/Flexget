import serializer from 'jest-glamor-react';
import { sheet } from 'emotion';

expect.addSnapshotSerializer(serializer(sheet));
